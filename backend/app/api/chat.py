"""
backend/app/api/chat.py

Repository Chat API Router for Phase 9d.
Provides grounded Q&A over the codebase with hybrid retrieval, call-graph expansion,
and mandatory source code citations [file:line-range].
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import crud
from app.db.session import get_db
from app.llm.client import (
    LLMInvalidResponseError,
    LLMTimeoutError,
    LLMUnavailableError,
    get_llm_client,
)
from app.rag.chat import ChatRequest, ChatResponse, RepositoryChatEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["Repository Chat"])


def get_chat_engine(settings: Settings = Depends(get_settings)) -> RepositoryChatEngine:
    """Dependency provider for RepositoryChatEngine."""
    client = get_llm_client(settings)
    return RepositoryChatEngine(settings=settings, client=client)


@router.post(
    "/{project_id}/chat",
    response_model=ChatResponse,
    summary="Ask a grounded question about the repository codebase",
    description=(
        "Retrieves relevant code chunks using vector similarity and call graph expansion, "
        "enforces a strict context token budget, and generates a grounded answer with "
        "mandatory [file:line-range] source citations. Explicitly states 'not enough information' "
        "if the codebase does not answer the question."
    ),
    responses={
        404: {"description": "Project not found"},
        503: {"description": "Local LLM server is unreachable"},
        504: {"description": "Local LLM generation timed out"},
        502: {"description": "Local LLM returned an invalid response"},
    },
)
async def chat_with_repository(
    project_id: str,
    payload: ChatRequest,
    chat_engine: RepositoryChatEngine = Depends(get_chat_engine),
    db: Session = Depends(get_db),
) -> ChatResponse:
    """Perform grounded repository Q&A."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )

    try:
        return await chat_engine.chat(
            project_id=project_id,
            message=payload.message,
            history=payload.history,
            top_k=payload.top_k,
            enable_graph_expansion=payload.enable_graph_expansion,
            db=db,
        )
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
        logger.exception("Error executing repository chat: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process chat query: {str(e)}",
        )
