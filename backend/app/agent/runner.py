"""
Background execution runner and status tracking for the agent workflow.
Executes the LangGraph StateGraph, streaming step-by-step progress,
updating database records, and providing live telemetry to the UI.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.agent.state import AnalysisState
from app.agent.workflow import create_analysis_workflow
from app.db import crud
from app.db.session import SessionLocal


# Global in-memory cache for live active run updates
_ACTIVE_RUNS: Dict[str, Dict[str, Any]] = {}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_pipeline_status(project_id: str) -> Dict[str, Any]:
    """
    Retrieve current pipeline execution status for a project.
    Checks live active in-memory cache first, falls back to latest database record.
    """
    if project_id in _ACTIVE_RUNS:
        return _ACTIVE_RUNS[project_id]

    with SessionLocal() as db:
        latest_run = crud.get_latest_analysis_run(db, project_id)
        if not latest_run:
            return {
                "project_id": project_id,
                "status": "idle",
                "step": "idle",
                "progress_percent": 0,
                "current_activity": "Ready for analysis",
                "error_message": None,
                "started_at": None,
                "completed_at": None,
            }

        return {
            "project_id": project_id,
            "run_id": latest_run.id,
            "status": latest_run.status,
            "step": latest_run.step,
            "progress_percent": latest_run.progress_percent,
            "current_activity": f"Current status: {latest_run.step}",
            "error_message": latest_run.error_message,
            "started_at": latest_run.started_at.isoformat() if latest_run.started_at else None,
            "completed_at": latest_run.completed_at.isoformat() if latest_run.completed_at else None,
        }


def execute_analysis_sync(project_id: str) -> Dict[str, Any]:
    """
    Execute the entire LangGraph agent workflow synchronously for a project.
    Can be run in a background thread/task or in automated tests.
    """
    with SessionLocal() as db:
        project = crud.get_project(db, project_id)
        if not project:
            raise ValueError(f"Project '{project_id}' not found.")

        project_path = Path(project.path)
        project_name = project.name

        # Create persistent run record in SQLite
        db_run = crud.create_analysis_run(
            db=db,
            project_id=project_id,
            status="running",
            step="Initializing agent workflow",
            progress_percent=5,
        )
        run_id = db_run.id

    # Initialize live tracking
    _ACTIVE_RUNS[project_id] = {
        "project_id": project_id,
        "run_id": run_id,
        "status": "running",
        "step": "Initializing",
        "progress_percent": 5,
        "current_activity": "Compiling LangGraph StateGraph agent...",
        "error_message": None,
        "started_at": _utc_now().isoformat(),
        "completed_at": None,
        "logs": ["Workflow execution started"],
    }

    initial_state: AnalysisState = {
        "project_id": project_id,
        "project_path": str(project_path),
        "project_name": project_name,
        "run_id": run_id,
        "status": "running",
        "step": "Initializing",
        "progress_percent": 5,
        "current_activity": "Starting LangGraph agent workflow",
        "error_message": None,
        "logs": ["LangGraph agent initialized"],
    }

    try:
        workflow_app = create_analysis_workflow()
        accumulated_state: Dict[str, Any] = dict(initial_state)

        # Stream node-by-node execution
        for event in workflow_app.stream(initial_state):
            for node_name, node_update in event.items():
                accumulated_state.update(node_update)

                step_name = node_update.get("step", node_name)
                pct = node_update.get("progress_percent", 50)
                activity = node_update.get("current_activity", f"Executing {node_name}...")

                # Update live memory
                _ACTIVE_RUNS[project_id]["step"] = step_name
                _ACTIVE_RUNS[project_id]["progress_percent"] = pct
                _ACTIVE_RUNS[project_id]["current_activity"] = activity
                _ACTIVE_RUNS[project_id]["logs"].append(f"[{node_name}] {activity}")

                # Update SQLite database
                with SessionLocal() as db:
                    crud.update_analysis_run(
                        db=db,
                        run_id=run_id,
                        step=step_name,
                        progress_percent=pct,
                    )

        # Mark completed
        finished_time = _utc_now()
        _ACTIVE_RUNS[project_id].update({
            "status": "completed",
            "step": "Completed",
            "progress_percent": 100,
            "current_activity": "Analysis complete! Graph, findings, vector index, and docs ready.",
            "completed_at": finished_time.isoformat(),
        })

        with SessionLocal() as db:
            crud.update_analysis_run(
                db=db,
                run_id=run_id,
                status="completed",
                step="Completed",
                progress_percent=100,
                completed_at=finished_time,
            )

        return accumulated_state

    except Exception as exc:
        err_msg = str(exc)
        _ACTIVE_RUNS[project_id].update({
            "status": "failed",
            "error_message": err_msg,
            "current_activity": f"Failed: {err_msg}",
        })

        with SessionLocal() as db:
            crud.update_analysis_run(
                db=db,
                run_id=run_id,
                status="failed",
                error_message=err_msg,
                completed_at=_utc_now(),
            )
        raise exc


async def execute_analysis_async(project_id: str) -> None:
    """
    Runs the synchronous pipeline execution in a thread pool executor
    to prevent blocking the FastAPI asynchronous event loop.
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, execute_analysis_sync, project_id)
