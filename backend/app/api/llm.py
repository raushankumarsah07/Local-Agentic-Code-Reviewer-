"""
LLM Explanation and Diagnostics API Router.
Provides endpoints for single finding explanation, sequential batch explanation, and LLM health diagnostics.
Maps custom LLM exceptions to appropriate HTTP error status codes (503, 504, 502).
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import crud
from app.db.session import get_db
from app.llm.client import (
    LlamaCppClient,
    LLMInvalidResponseError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.llm.explainer import FindingExplainerService
from app.llm.schemas import (
    BatchExplainRequest,
    BatchExplainResponse,
    ExplanationResponse,
    FindingExplanation,
    LLMHealthResponse,
)

router = APIRouter(tags=["Local LLM Explanation"])


def get_explainer_service(settings: Settings = Depends(get_settings)) -> FindingExplainerService:
    """Dependency provider for FindingExplainerService."""
    client = LlamaCppClient(settings)
    return FindingExplainerService(client=client, settings=settings)


@router.post(
    "/findings/{finding_id}/explain",
    response_model=ExplanationResponse,
    summary="Generate or fetch grounded LLM explanation for a finding",
    description="Invokes local llama-server to explain a static analysis finding. Returns cached explanation if already available unless force=true.",
    responses={
        503: {"description": "Local LLM server is unreachable or offline"},
        504: {"description": "Local LLM request timed out"},
        502: {"description": "Local LLM returned an invalid HTTP response"},
        404: {"description": "Finding not found"},
    },
)
async def explain_finding_endpoint(
    finding_id: int,
    force: bool = Query(default=False, description="Whether to bypass cache and regenerate explanation"),
    explainer: FindingExplainerService = Depends(get_explainer_service),
    db: Session = Depends(get_db),
) -> ExplanationResponse:
    """Generate structured AI explanation for a single finding."""
    finding = crud.get_finding(db, finding_id)
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding with ID '{finding_id}' not found.",
        )

    try:
        return await explainer.explain_finding(finding_id=finding_id, db=db, force=force)
    except LLMUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except LLMTimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(e),
        )
    except LLMInvalidResponseError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error explaining finding: {str(e)}",
        )


@router.get(
    "/findings/{finding_id}/explanation",
    response_model=ExplanationResponse,
    summary="Retrieve cached LLM explanation for a finding",
    description="Fetches previously persisted AI explanation from the database without triggering model inference.",
    responses={
        404: {"description": "Explanation not yet generated for this finding"},
    },
)
async def get_finding_explanation_endpoint(
    finding_id: int,
    db: Session = Depends(get_db),
) -> ExplanationResponse:
    """Fetch stored AI explanation for a finding."""
    finding = crud.get_finding(db, finding_id)
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding with ID '{finding_id}' not found.",
        )

    cached = crud.get_finding_explanation(db, finding_id)
    if not cached:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No explanation has been generated for finding ID '{finding_id}'. Call POST /findings/{finding_id}/explain first.",
        )

    import json
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


@router.post(
    "/projects/{project_id}/explain-batch",
    response_model=BatchExplainResponse,
    summary="Batch explain findings sequentially for a project",
    description="Processes findings one at a time to minimize memory usage on local developer machines.",
)
async def explain_batch_endpoint(
    project_id: str,
    request: BatchExplainRequest,
    explainer: FindingExplainerService = Depends(get_explainer_service),
    db: Session = Depends(get_db),
) -> BatchExplainResponse:
    """Run sequential batch explanation for findings in a project."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )

    try:
        return await explainer.explain_findings_batch(
            project_id=project_id,
            db=db,
            severity_filter=request.severity_filter,
            limit=request.limit or 10,
            force=request.force,
        )
    except LLMUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )


@router.get(
    "/llm/health",
    response_model=LLMHealthResponse,
    summary="Check local LLM and embedding server connectivity",
    description="Probes local llama-server endpoints and returns availability diagnostics with exact start commands if offline.",
)
async def llm_health_endpoint(
    settings: Settings = Depends(get_settings),
) -> LLMHealthResponse:
    """Perform connection probe against local llama-server."""
    client = LlamaCppClient(settings)
    probe_result = await client.health_check()
    return LLMHealthResponse(**probe_result)
