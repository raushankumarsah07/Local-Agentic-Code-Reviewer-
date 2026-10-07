"""
Health check and system diagnostic API router.
"""

from typing import Dict, Any, List
import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import Settings, get_settings


router = APIRouter(prefix="/health", tags=["Health"])


class HealthResponse(BaseModel):
    """Schema for health status response."""
    status: str
    app_name: str
    environment: str
    workspace_dir: str
    ollama_service: Dict[str, Any]


@router.get("", response_model=HealthResponse)
async def check_health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """
    Check server status and local Ollama runtime availability.
    Provides clear startup diagnostics if Ollama is not running or models are missing.
    """
    ollama_info: Dict[str, Any] = {
        "status": "unreachable",
        "url": settings.OLLAMA_BASE_URL,
        "configured_llm_model": settings.LLM_MODEL,
        "configured_embedding_model": settings.EMBEDDING_MODEL,
        "llm_model_downloaded": False,
        "embedding_model_downloaded": False,
        "available_models": [],
        "message": "Ollama is not running. Run 'ollama serve' locally when you are ready for Phase 8+ (LLM/RAG).",
    }

    # Test local Ollama connection with a quick timeout (1.5 seconds)
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models: List[str] = [m.get("name", "") for m in data.get("models", [])]
                ollama_info["status"] = "connected"
                ollama_info["available_models"] = models
                
                # Check if configured models are downloaded
                # Model names in Ollama can be 'model:latest' or 'model'
                def match_model(target: str, model_list: List[str]) -> bool:
                    target_clean = target.split(":")[0].lower()
                    return any(target_clean in m.lower() for m in model_list)

                llm_found = match_model(settings.LLM_MODEL, models)
                emb_found = match_model(settings.EMBEDDING_MODEL, models)

                ollama_info["llm_model_downloaded"] = llm_found
                ollama_info["embedding_model_downloaded"] = emb_found

                if not llm_found:
                    ollama_info["message"] = (
                        f"Ollama is running, but LLM '{settings.LLM_MODEL}' is not pulled. "
                        f"Run 'ollama pull {settings.LLM_MODEL}'"
                    )
                elif not emb_found:
                    ollama_info["message"] = (
                        f"Ollama is running, but embedding model '{settings.EMBEDDING_MODEL}' is not pulled. "
                        f"Run 'ollama pull {settings.EMBEDDING_MODEL}'"
                    )
                else:
                    ollama_info["message"] = "All services and configured models are ready."
    except Exception:
        # Ollama connection failure is expected in Phase 1 if not yet started
        pass

    return HealthResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        environment=settings.APP_ENV,
        workspace_dir=str(settings.WORKSPACE_DIR.resolve()),
        ollama_service=ollama_info,
    )
