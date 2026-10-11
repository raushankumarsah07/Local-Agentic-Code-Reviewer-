"""
Pydantic schemas for LLM structured output, finding explanations, and API contracts.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class FindingExplanation(BaseModel):
    """
    Structured, grounded explanation for a static analysis finding.
    Enforces strict field boundaries and character length constraints.
    """
    problem: str = Field(
        ...,
        max_length=500,
        description="Clear, concise statement of the problem or defect",
    )
    risk: str = Field(
        ...,
        max_length=500,
        description="Practical risk, vulnerability impact, or architectural consequence if unaddressed",
    )
    recommended_fix: str = Field(
        ...,
        max_length=1000,
        description="Actionable, concrete remediation steps or code refactoring advice",
    )
    confidence_note: str = Field(
        ...,
        max_length=300,
        description="Assessment of confidence and why manual human developer verification is needed",
    )


class ExplanationResponse(BaseModel):
    """API Response schema for a single finding explanation."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    finding_id: int
    model_name: str
    prompt_version: str
    explanation: FindingExplanation
    latency_ms: int
    tokens: int
    status: str  # 'success', 'repaired', 'fallback', 'cached'
    created_at: datetime


class BatchExplainRequest(BaseModel):
    """Request schema for batch explanation generation."""
    severity_filter: Optional[str] = Field(
        default=None,
        description="Optional severity filter (e.g. 'Critical', 'High')",
    )
    limit: Optional[int] = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum findings to process in this batch (processed sequentially)",
    )
    force: bool = Field(
        default=False,
        description="Whether to bypass cache and regenerate explanations",
    )


class BatchExplainItemResult(BaseModel):
    """Result for an individual finding within a batch run."""
    finding_id: int
    title: str
    severity: str
    status: str
    latency_ms: int
    explanation: Optional[FindingExplanation] = None
    error: Optional[str] = None


class BatchExplainResponse(BaseModel):
    """Summary of batch explanation processing."""
    project_id: str
    total_processed: int
    successful: int
    failed: int
    fallback_count: int
    total_latency_ms: int
    results: List[BatchExplainItemResult]


class LLMHealthResponse(BaseModel):
    """Diagnostic health status report for local LLM runtime and embedding service."""
    status: str  # 'connected' | 'unreachable'
    backend: str  # 'llama.cpp'
    base_url: str
    model_name: str
    context_size: int
    server_online: bool
    embedding_server_online: bool
    message: str
    start_command: str
    embedding_start_command: str
