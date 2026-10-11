"""
Local LLM Integration Module for llama.cpp / llama-server.
"""

from app.llm.client import (
    LLMClient,
    LlamaCppClient,
    OllamaClient,
    get_llm_client,
    LLMError,
    LLMUnavailableError,
    LLMTimeoutError,
    LLMInvalidResponseError,
    LLMResponse,
)
from app.llm.explainer import FindingExplainerService
from app.llm.prompts import (
    build_explanation_prompt,
    get_system_prompt,
    get_repair_prompt,
    strip_thinking_tags,
    truncate_code_snippet,
    PROMPT_VERSION,
)
from app.llm.schemas import (
    FindingExplanation,
    ExplanationResponse,
    BatchExplainRequest,
    BatchExplainResponse,
    BatchExplainItemResult,
    LLMHealthResponse,
)

__all__ = [
    "LLMClient",
    "LlamaCppClient",
    "OllamaClient",
    "get_llm_client",
    "LLMError",
    "LLMUnavailableError",
    "LLMTimeoutError",
    "LLMInvalidResponseError",
    "LLMResponse",
    "FindingExplainerService",
    "FindingExplanation",
    "ExplanationResponse",
    "BatchExplainRequest",
    "BatchExplainResponse",
    "BatchExplainItemResult",
    "LLMHealthResponse",
    "build_explanation_prompt",
    "get_system_prompt",
    "get_repair_prompt",
    "strip_thinking_tags",
    "truncate_code_snippet",
    "PROMPT_VERSION",
]
