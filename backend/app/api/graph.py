"""
Dependency Graph API Router.
Provides endpoints to generate, query, and export NetworkX architecture graphs.
"""

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import crud
from app.db.session import get_db
from app.graph.builder import DependencyGraphBuilder, GraphData

router = APIRouter(prefix="/projects", tags=["Architecture Graph"])


@router.get(
    "/{project_id}/graph",
    response_model=GraphData,
    summary="Get architecture dependency graph",
    description="Builds and exports a NetworkX directed graph of files (nodes) and resolved imports (edges) with in/out degree metrics.",
)
async def get_project_graph(
    project_id: str,
    include_external: bool = Query(True, description="Whether to include external libraries as nodes"),
    db: Session = Depends(get_db),
) -> GraphData:
    """Generate and return architecture dependency graph for the project."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )

    project_root = Path(project.path)
    if not project_root.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project directory '{project.path}' does not exist on disk.",
        )

    builder = DependencyGraphBuilder(project_root=project_root, project_id=project_id)
    graph_data = builder.export_json(include_external=include_external)

    return graph_data
