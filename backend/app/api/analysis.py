"""
Analysis & Agent Workflow API Router.
Provides background agent execution, step-by-step status monitoring,
and documentation retrieval & export endpoints.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.runner import execute_analysis_async, get_pipeline_status
from app.db import crud
from app.db.session import get_db

router = APIRouter(prefix="/projects", tags=["Agent Workflow & Analysis"])


# --- Schemas ---

class AnalysisTriggerResponse(BaseModel):
    """Response returned upon triggering the agent analysis workflow."""
    project_id: str
    status: str
    step: str
    progress_percent: int
    message: str


class AnalysisStatusResponse(BaseModel):
    """Detailed pipeline execution status and progress tracking."""
    project_id: str
    run_id: Optional[int] = None
    status: str
    step: str
    progress_percent: int
    current_activity: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    logs: List[str] = Field(default_factory=list)


class DocumentationResponse(BaseModel):
    """Generated architectural documentation and structured summary."""
    project_id: str
    overview_md: str
    structure: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None


# --- Endpoints ---

@router.post(
    "/{project_id}/analyze",
    response_model=AnalysisTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger full agentic repository analysis (Phase 10)",
    description=(
        "Executes the full LangGraph agent workflow in the background: "
        "scanning -> AST parsing -> graph building -> static quality & security checks -> "
        "ChromaDB indexing -> finding context enrichment -> hierarchical documentation generation."
    ),
)
async def trigger_analysis(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> AnalysisTriggerResponse:
    """Trigger background agent workflow for a project."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )

    current_status = get_pipeline_status(project_id)
    if current_status.get("status") == "running":
        return AnalysisTriggerResponse(
            project_id=project_id,
            status="running",
            step=current_status.get("step", "running"),
            progress_percent=current_status.get("progress_percent", 50),
            message="Analysis pipeline is already running.",
        )

    # Queue execution as a non-blocking background task
    background_tasks.add_task(execute_analysis_async, project_id)

    return AnalysisTriggerResponse(
        project_id=project_id,
        status="running",
        step="Initializing",
        progress_percent=5,
        message="Agent analysis workflow initiated successfully in background.",
    )


@router.get(
    "/{project_id}/status",
    response_model=AnalysisStatusResponse,
    summary="Get step-by-step agent workflow progress",
    description="Polls live step progress (0-100%), active activity, logs, and completion status.",
)
async def get_analysis_status(project_id: str, db: Session = Depends(get_db)) -> AnalysisStatusResponse:
    """Retrieve current pipeline execution progress."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )

    status_data = get_pipeline_status(project_id)
    return AnalysisStatusResponse(
        project_id=project_id,
        run_id=status_data.get("run_id"),
        status=status_data.get("status", "idle"),
        step=status_data.get("step", "idle"),
        progress_percent=status_data.get("progress_percent", 0),
        current_activity=status_data.get("current_activity"),
        error_message=status_data.get("error_message"),
        started_at=status_data.get("started_at"),
        completed_at=status_data.get("completed_at"),
        logs=status_data.get("logs", []),
    )


@router.get(
    "/{project_id}/docs",
    response_model=DocumentationResponse,
    summary="Get generated architectural documentation",
    description="Retrieves the generated Markdown documentation and hierarchical map-reduce structure.",
)
async def get_project_documentation(project_id: str, db: Session = Depends(get_db)) -> DocumentationResponse:
    """Retrieve generated architectural documentation for a project."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )

    doc_record = crud.get_project_doc(db, project_id)
    if not doc_record:
        # Check if file exists on disk
        disk_path = Path(project.path) / "docs" / "ARCHITECTURE.md"
        if disk_path.exists():
            content = disk_path.read_text(encoding="utf-8")
            return DocumentationResponse(
                project_id=project_id,
                overview_md=content,
                structure=None,
                created_at=None,
            )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documentation has not yet been generated for project '{project_id}'. Run analysis first.",
        )

    structure_dict = None
    if doc_record.summary_data:
        try:
            structure_dict = json.loads(doc_record.summary_data)
        except Exception:
            pass

    return DocumentationResponse(
        project_id=project_id,
        overview_md=doc_record.overview_md,
        structure=structure_dict,
        created_at=doc_record.created_at.isoformat() if doc_record.created_at else None,
    )


@router.get(
    "/{project_id}/docs/download",
    summary="Download documentation as Markdown file",
    description="Returns the generated ARCHITECTURE.md file as a downloadable file attachment.",
)
async def download_documentation(project_id: str, db: Session = Depends(get_db)):
    """Download Markdown documentation."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )

    doc_record = crud.get_project_doc(db, project_id)
    content = ""
    if doc_record:
        content = doc_record.overview_md
    else:
        disk_path = Path(project.path) / "docs" / "ARCHITECTURE.md"
        if disk_path.exists():
            content = disk_path.read_text(encoding="utf-8")
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Documentation not generated yet.",
            )

    safe_filename = f"{project.name}_ARCHITECTURE.md"
    return Response(
        content=content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )
