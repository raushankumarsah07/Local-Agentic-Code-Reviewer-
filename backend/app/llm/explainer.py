"""
Finding Explainer Service.
Orchestrates prompt construction, client invocation, structured output validation,
single-retry repair, fallback handling, caching, and sequential batch execution.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import crud
from app.db.models import Finding, FindingExplanation as FindingExplanationModel
from app.llm.client import (
    LLMClient,
    LlamaCppClient,
    LLMError,
    LLMInvalidResponseError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.llm.prompts import (
    PROMPT_VERSION,
    build_explanation_prompt,
    get_repair_prompt,
    strip_thinking_tags,
)
from app.llm.schemas import (
    BatchExplainItemResult,
    BatchExplainResponse,
    ExplanationResponse,
    FindingExplanation,
)

logger = logging.getLogger(__name__)


class FindingExplainerService:
    """
    Service responsible for explaining static analysis findings using local LLM.
    Enforces deterministic facts from deterministic analyzers; uses LLM solely for explanation.
    """

    def __init__(
        self,
        client: Optional[LLMClient] = None,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.client = client or LlamaCppClient(self.settings)

    def _extract_source_code_context(
        self,
        finding: Finding,
        context_padding: int = 15,
    ) -> str:
        """
        Load code from the project file on disk surrounding the finding line range.
        Falls back to finding.evidence_snippet if file cannot be read.
        """
        if finding.project and finding.project.path:
            full_file_path = Path(finding.project.path) / finding.file
            if full_file_path.exists() and full_file_path.is_file():
                try:
                    with open(full_file_path, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()

                    start_idx = max(0, finding.start_line - 1 - context_padding)
                    end_idx = min(len(lines), finding.end_line + context_padding)
                    return "".join(lines[start_idx:end_idx])
                except Exception as e:
                    logger.debug("Failed reading file %s: %s", full_file_path, e)

        return finding.evidence_snippet or "# No source snippet available"

    def _parse_and_validate_json(self, raw_content: str) -> FindingExplanation:
        """Strip thinking tags, parse JSON, and validate against Pydantic model."""
        clean_json_str = strip_thinking_tags(raw_content)
        data = json.loads(clean_json_str)
        return FindingExplanation.model_validate(data)

    async def explain_finding(
        self,
        finding_id: int,
        db: Session,
        force: bool = False,
    ) -> ExplanationResponse:
        """
        Explain a single finding by ID.
        Checks cache first unless force=True.
        Retries once with repair prompt if JSON is invalid.
        Falls back safely without crashing if model output is unrecoverable.
        """
        finding = crud.get_finding(db, finding_id)
        if not finding:
            raise ValueError(f"Finding with ID {finding_id} not found.")

        model_name = getattr(self.client, "model_name", self.settings.LLM_MODEL)

        # 1. Cache Check
        if not force:
            cached = crud.get_finding_explanation(db, finding_id, model_name=model_name)
            if cached:
                try:
                    parsed_exp = FindingExplanation.model_validate(json.loads(cached.explanation))
                    return ExplanationResponse(
                        id=cached.id,
                        finding_id=cached.finding_id,
                        model_name=cached.model_name,
                        prompt_version=cached.prompt_version,
                        explanation=parsed_exp,
                        latency_ms=cached.latency_ms,
                        tokens=cached.tokens,
                        status=cached.status,
                        created_at=cached.created_at,
                    )
                except Exception:
                    # If cached record is malformed, proceed to regenerate
                    pass

        # If force=True, clean existing cache records
        if force:
            crud.delete_finding_explanations(db, finding_id)

        # 2. Extract code context and build prompt
        code_context = self._extract_source_code_context(finding)
        messages = build_explanation_prompt(
            finding_title=finding.title,
            finding_type=finding.type,
            severity=finding.severity,
            file_path=finding.file,
            start_line=finding.start_line,
            end_line=finding.end_line,
            code_snippet=code_context,
            source_tool=finding.source_tool,
            context_size=self.settings.LLM_CONTEXT_SIZE,
        )

        schema = FindingExplanation.model_json_schema()

        # 3. Call LLM Client (Primary Attempt)
        primary_response = await self.client.chat(
            messages=messages,
            response_schema=schema,
        )

        explanation_obj: Optional[FindingExplanation] = None
        status = "success"
        total_latency_ms = primary_response.latency_ms
        total_tokens = primary_response.total_tokens

        try:
            explanation_obj = self._parse_and_validate_json(primary_response.content)
        except (json.JSONDecodeError, ValidationError) as primary_err:
            logger.warning(
                "Primary LLM output for finding %d was invalid JSON: %s. Initiating repair prompt...",
                finding_id,
                primary_err,
            )

            # 4. Single-Retry Repair Attempt
            repair_user_content = get_repair_prompt(
                invalid_content=primary_response.content,
                error_detail=str(primary_err),
            )
            repair_messages = list(messages) + [
                {"role": "assistant", "content": primary_response.content},
                {"role": "user", "content": repair_user_content},
            ]

            try:
                repair_response = await self.client.chat(
                    messages=repair_messages,
                    response_schema=schema,
                    temperature=0.0,  # Zero temperature for maximum formatting strictness
                )
                total_latency_ms += repair_response.latency_ms
                total_tokens += repair_response.total_tokens

                explanation_obj = self._parse_and_validate_json(repair_response.content)
                status = "repaired"
                logger.info("Successfully repaired JSON for finding %d.", finding_id)
            except Exception as repair_err:
                logger.error(
                    "Repair attempt failed for finding %d: %s. Using safe fallback object.",
                    finding_id,
                    repair_err,
                )
                # 5. Safe Fallback Object (Never crashes)
                status = "fallback"
                explanation_obj = FindingExplanation(
                    problem=f"Potential {finding.type} defect: {finding.title}.",
                    risk="Manual developer verification is recommended to assess architectural risk.",
                    recommended_fix=(
                        f"Inspect {finding.file} lines {finding.start_line}-{finding.end_line}. "
                        "Review tool guidelines and apply parameterization or refactoring as needed."
                    ),
                    confidence_note="Explanation generated by safe fallback handler due to unparseable model output.",
                )

        # 6. Persist to DB
        saved_record = crud.save_finding_explanation(
            db=db,
            finding_id=finding_id,
            model_name=model_name,
            prompt_version=PROMPT_VERSION,
            explanation_json=explanation_obj.model_dump_json(),
            latency_ms=total_latency_ms,
            tokens=total_tokens,
            status=status,
        )

        return ExplanationResponse(
            id=saved_record.id,
            finding_id=saved_record.finding_id,
            model_name=saved_record.model_name,
            prompt_version=saved_record.prompt_version,
            explanation=explanation_obj,
            latency_ms=saved_record.latency_ms,
            tokens=saved_record.tokens,
            status=saved_record.status,
            created_at=saved_record.created_at,
        )

    async def explain_findings_batch(
        self,
        project_id: str,
        db: Session,
        severity_filter: Optional[str] = None,
        limit: int = 10,
        force: bool = False,
    ) -> BatchExplainResponse:
        """
        Explain multiple findings sequentially (one request at a time to prevent RAM overload).
        """
        findings, _ = crud.get_project_findings(
            db=db,
            project_id=project_id,
            severity=severity_filter,
            limit=limit,
        )

        results: List[BatchExplainItemResult] = []
        successful = 0
        failed = 0
        fallback_count = 0
        total_latency_ms = 0

        for finding in findings:
            try:
                res = await self.explain_finding(
                    finding_id=finding.id,
                    db=db,
                    force=force,
                )
                total_latency_ms += res.latency_ms

                if res.status == "fallback":
                    fallback_count += 1
                else:
                    successful += 1

                results.append(
                    BatchExplainItemResult(
                        finding_id=finding.id,
                        title=finding.title,
                        severity=finding.severity,
                        status=res.status,
                        latency_ms=res.latency_ms,
                        explanation=res.explanation,
                        error=None,
                    )
                )
            except Exception as err:
                failed += 1
                logger.error("Failed explaining finding %d in batch: %s", finding.id, err)
                results.append(
                    BatchExplainItemResult(
                        finding_id=finding.id,
                        title=finding.title,
                        severity=finding.severity,
                        status="error",
                        latency_ms=0,
                        explanation=None,
                        error=str(err),
                    )
                )

        return BatchExplainResponse(
            project_id=project_id,
            total_processed=len(findings),
            successful=successful,
            failed=failed,
            fallback_count=fallback_count,
            total_latency_ms=total_latency_ms,
            results=results,
        )
