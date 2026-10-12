"""
Database CRUD (Create, Read, Update, Delete) utility functions.
"""

from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import (
    AnalysisRun,
    ChatMessage,
    ChunkMeta,
    CodeEntity,
    Finding,
    FindingExplanation,
    GraphEdge,
    Project,
    ProjectDoc,
    ProjectFile,
)


def create_project(
    db: Session,
    project_id: str,
    name: str,
    path: str,
    total_files: int = 0,
    total_lines: int = 0,
    total_size_bytes: int = 0,
) -> Project:
    """
    Create and persist a new project record.
    """
    project = Project(
        id=project_id,
        name=name,
        path=path,
        total_files=total_files,
        total_lines=total_lines,
        total_size_bytes=total_size_bytes,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def get_project(db: Session, project_id: str) -> Optional[Project]:
    """
    Retrieve a project record by its unique identifier.
    """
    return db.query(Project).filter(Project.id == project_id).first()


def list_projects(db: Session) -> List[Project]:
    """
    Retrieve all projects ordered by newest first.
    """
    return db.query(Project).order_by(Project.created_at.desc()).all()


def delete_project(db: Session, project_id: str) -> bool:
    """
    Delete a project and cascade delete all associated file records.
    """
    project = get_project(db, project_id)
    if not project:
        return False
    db.delete(project)
    db.commit()
    return True


def save_project_files(
    db: Session,
    project_id: str,
    files_data: List[dict],
) -> List[ProjectFile]:
    """
    Bulk insert file records for a project. Purges previous records to ensure idempotency.
    """
    db.query(ProjectFile).filter(ProjectFile.project_id == project_id).delete()
    db.commit()

    file_records = [
        ProjectFile(
            project_id=project_id,
            path=item["path"],
            language=item["language"],
            size_bytes=item["size_bytes"],
            line_count=item["line_count"],
        )
        for item in files_data
    ]
    db.add_all(file_records)
    db.commit()
    return file_records


def get_project_files(
    db: Session,
    project_id: str,
    language: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> Tuple[List[ProjectFile], int]:
    """
    Retrieve files belonging to a project, with optional language filtering and pagination.
    Returns (files_list, total_count).
    """
    query = db.query(ProjectFile).filter(ProjectFile.project_id == project_id)
    if language:
        query = query.filter(func.lower(ProjectFile.language) == language.lower())

    total_count = query.count()

    query = query.order_by(ProjectFile.path.asc())
    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    return query.all(), total_count


def get_project_language_stats(db: Session, project_id: str) -> dict[str, int]:
    """
    Aggregate file counts grouped by programming/markup language for a project.
    """
    results = (
        db.query(ProjectFile.language, func.count(ProjectFile.id))
        .filter(ProjectFile.project_id == project_id)
        .group_by(ProjectFile.language)
        .all()
    )
    return {lang: count for lang, count in results}


def save_code_entities(
    db: Session,
    project_id: str,
    entities_data: List[dict],
) -> List[CodeEntity]:
    """
    Bulk insert extracted AST code entities (classes, functions, methods, imports).
    Purges previous records to ensure idempotency.
    """
    db.query(CodeEntity).filter(CodeEntity.project_id == project_id).delete()
    db.commit()

    entity_records = [
        CodeEntity(
            project_id=project_id,
            file_path=item["file_path"],
            entity_type=item["entity_type"],
            name=item["name"],
            parent_name=item.get("parent_name"),
            start_line=item.get("start_line", 0),
            end_line=item.get("end_line", 0),
            details=item.get("details"),
        )
        for item in entities_data
    ]
    db.add_all(entity_records)
    db.commit()
    return entity_records


def get_project_entities(
    db: Session,
    project_id: str,
    entity_type: Optional[str] = None,
) -> List[CodeEntity]:
    """
    Retrieve all parsed AST entities for a project, optionally filtered by type.
    """
    query = db.query(CodeEntity).filter(CodeEntity.project_id == project_id)
    if entity_type:
        query = query.filter(CodeEntity.entity_type == entity_type)
    return query.order_by(CodeEntity.file_path.asc(), CodeEntity.start_line.asc()).all()


def get_file_entities(
    db: Session,
    project_id: str,
    file_path: str,
) -> List[CodeEntity]:
    """
    Retrieve all parsed AST entities belonging to a specific file.
    """
    return (
        db.query(CodeEntity)
        .filter(CodeEntity.project_id == project_id, CodeEntity.file_path == file_path)
        .order_by(CodeEntity.start_line.asc())
        .all()
    )


def save_graph_edges(
    db: Session,
    project_id: str,
    edges_data: List[dict],
) -> List[GraphEdge]:
    """
    Bulk persist dependency edges for a project. Purges previous records to ensure idempotency.
    """
    db.query(GraphEdge).filter(GraphEdge.project_id == project_id).delete()
    db.commit()

    import json
    edge_records = [
        GraphEdge(
            project_id=project_id,
            source=item["source"],
            target=item["target"],
            edge_type=item.get("edge_type", "import"),
            is_external=item.get("is_external", False),
            imported_symbols=(
                json.dumps(item["imported_symbols"])
                if isinstance(item.get("imported_symbols"), (list, dict))
                else item.get("imported_symbols")
            ),
            line_number=item.get("line_number"),
        )
        for item in edges_data
    ]
    db.add_all(edge_records)
    db.commit()
    return edge_records


def get_project_edges(
    db: Session,
    project_id: str,
) -> List[GraphEdge]:
    """
    Retrieve stored dependency edges for a project.
    """
    return db.query(GraphEdge).filter(GraphEdge.project_id == project_id).all()


# --- Findings CRUD ---

def save_findings(
    db: Session,
    project_id: str,
    findings_data: List[dict],
    replace_type: Optional[str] = None,
) -> List[Finding]:
    """
    Save static analysis findings to the database.
    If `replace_type` is specified, deletes existing findings of that type for the project first.
    """
    if replace_type:
        delete_project_findings(db, project_id, finding_type=replace_type)

    finding_records = [
        Finding(
            project_id=project_id,
            type=item["type"],
            severity=item["severity"],
            title=item["title"],
            file=item["file"],
            start_line=item["start_line"],
            end_line=item["end_line"],
            evidence_snippet=item.get("evidence_snippet"),
            source_tool=item.get("source_tool", "analyzer"),
            explanation=item.get("explanation"),
        )
        for item in findings_data
    ]
    db.add_all(finding_records)
    db.commit()
    return finding_records


def get_project_findings(
    db: Session,
    project_id: str,
    finding_type: Optional[str] = None,
    severity: Optional[str] = None,
    file_path: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> Tuple[List[Finding], int]:
    """
    Retrieve findings for a project with optional filtering by type, severity, or file.
    Returns (findings_list, total_count).
    """
    query = db.query(Finding).filter(Finding.project_id == project_id)

    if finding_type:
        query = query.filter(Finding.type == finding_type)
    if severity:
        query = query.filter(func.lower(Finding.severity) == severity.lower())
    if file_path:
        query = query.filter(Finding.file == file_path)

    total_count = query.count()
    query = query.order_by(Finding.id.asc())

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    return query.all(), total_count


def delete_project_findings(
    db: Session,
    project_id: str,
    finding_type: Optional[str] = None,
) -> int:
    """
    Delete findings for a project, optionally filtered by finding type.
    Returns the number of deleted records.
    """
    query = db.query(Finding).filter(Finding.project_id == project_id)
    if finding_type:
        query = query.filter(Finding.type == finding_type)
    count = query.delete(synchronize_session=False)
    db.commit()
    return count


def get_findings_summary(db: Session, project_id: str) -> dict:
    """
    Aggregate counts of findings by severity and type for a project.
    """
    severity_counts = (
        db.query(Finding.severity, func.count(Finding.id))
        .filter(Finding.project_id == project_id)
        .group_by(Finding.severity)
        .all()
    )
    type_counts = (
        db.query(Finding.type, func.count(Finding.id))
        .filter(Finding.project_id == project_id)
        .group_by(Finding.type)
        .all()
    )
    total_count = db.query(Finding).filter(Finding.project_id == project_id).count()

    return {
        "total": total_count,
        "by_severity": {sev: count for sev, count in severity_counts},
        "by_type": {t: count for t, count in type_counts},
    }


def get_finding(db: Session, finding_id: int) -> Optional[Finding]:
    """Retrieve an individual finding by its primary key ID."""
    return db.query(Finding).filter(Finding.id == finding_id).first()


# --- Finding Explanations CRUD (Phase 8) ---

def get_finding_explanation(
    db: Session,
    finding_id: int,
    model_name: Optional[str] = None,
) -> Optional[FindingExplanation]:
    """
    Retrieve cached LLM explanation for a finding.
    If model_name is provided, matches that specific model; otherwise returns latest.
    """
    query = (
        db.query(FindingExplanation)
        .filter(FindingExplanation.finding_id == finding_id)
        .order_by(FindingExplanation.created_at.desc())
    )
    if model_name:
        query = query.filter(FindingExplanation.model_name == model_name)
    return query.first()


def save_finding_explanation(
    db: Session,
    finding_id: int,
    model_name: str,
    prompt_version: str = "v1.0",
    explanation_json: str = "{}",
    latency_ms: int = 0,
    tokens: int = 0,
    status: str = "success",
) -> FindingExplanation:
    """
    Persist an AI explanation record for a static analysis finding.
    Also syncs the finding.explanation field for backwards compatibility.
    """
    record = FindingExplanation(
        finding_id=finding_id,
        model_name=model_name,
        prompt_version=prompt_version,
        explanation=explanation_json,
        latency_ms=latency_ms,
        tokens=tokens,
        status=status,
    )
    db.add(record)

    # Sync summary text into finding.explanation if finding exists
    finding = get_finding(db, finding_id)
    if finding:
        import json
        try:
            parsed = json.loads(explanation_json)
            finding.explanation = (
                f"{parsed.get('problem', '')} Risk: {parsed.get('risk', '')} "
                f"Fix: {parsed.get('recommended_fix', '')}"
            )
        except Exception:
            finding.explanation = explanation_json

    db.commit()
    db.refresh(record)
    return record


def delete_finding_explanations(db: Session, finding_id: int) -> int:
    """Delete all cached explanations for a finding (used when force=True)."""
    count = (
        db.query(FindingExplanation)
        .filter(FindingExplanation.finding_id == finding_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return count


# --- AnalysisRun Tracking ---

def create_analysis_run(
    db: Session,
    project_id: str,
    status: str = "running",
    step: str = "initialized",
    progress_percent: int = 0,
) -> AnalysisRun:
    """Create a new pipeline execution run record."""
    run = AnalysisRun(
        project_id=project_id,
        status=status,
        step=step,
        progress_percent=progress_percent,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def get_latest_analysis_run(db: Session, project_id: str) -> Optional[AnalysisRun]:
    """Retrieve the most recent analysis run for a project."""
    return (
        db.query(AnalysisRun)
        .filter(AnalysisRun.project_id == project_id)
        .order_by(AnalysisRun.started_at.desc())
        .first()
    )


def update_analysis_run(
    db: Session,
    run_id: int,
    status: Optional[str] = None,
    step: Optional[str] = None,
    progress_percent: Optional[int] = None,
    error_message: Optional[str] = None,
    completed_at: Optional[datetime] = None,
) -> Optional[AnalysisRun]:
    """Update execution status and progress percent for a run."""
    run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
    if not run:
        return None

    if status is not None:
        run.status = status
    if step is not None:
        run.step = step
    if progress_percent is not None:
        run.progress_percent = progress_percent
    if error_message is not None:
        run.error_message = error_message
    if completed_at is not None:
        run.completed_at = completed_at

    db.commit()
    db.refresh(run)
    return run


# --- Project Documentation ---

def save_project_doc(
    db: Session,
    project_id: str,
    overview_md: str,
    summary_data: Optional[str] = None,
) -> ProjectDoc:
    """Save or update generated project architectural documentation."""
    existing = db.query(ProjectDoc).filter(ProjectDoc.project_id == project_id).first()
    if existing:
        existing.overview_md = overview_md
        if summary_data is not None:
            existing.summary_data = summary_data
        db.commit()
        db.refresh(existing)
        return existing

    doc = ProjectDoc(
        project_id=project_id,
        overview_md=overview_md,
        summary_data=summary_data,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def get_project_doc(db: Session, project_id: str) -> Optional[ProjectDoc]:
    """Retrieve generated architectural documentation for a project."""
    return db.query(ProjectDoc).filter(ProjectDoc.project_id == project_id).first()

