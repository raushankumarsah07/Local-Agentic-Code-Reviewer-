"""
Findings and Static Analysis API Router.
Provides endpoints to trigger complexity analysis, list findings with filters, and fetch aggregate summaries.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.analysis.architecture import ArchitectureAnalyzer
from app.analysis.complexity import ComplexityAnalyzer, ComplexityThresholds
from app.analysis.dead_code import DeadCodeAnalyzer
from app.analysis.security import SecurityAnalyzer
from app.db import crud
from app.db.session import get_db

router = APIRouter(prefix="/projects", tags=["Findings & Static Analysis"])


# --- Pydantic Request & Response Schemas ---

class FindingResponse(BaseModel):
    """Schema for an individual code quality or security finding."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: str
    type: str
    severity: str
    title: str
    file: str
    start_line: int
    end_line: int
    evidence_snippet: Optional[str] = None
    source_tool: str
    explanation: Optional[str] = None
    created_at: datetime


class FindingsListResponse(BaseModel):
    """List response for findings with pagination metadata."""
    project_id: str
    total: int
    count: int
    findings: List[FindingResponse]


class FindingsSummaryResponse(BaseModel):
    """Summary metrics of findings grouped by severity and category."""
    project_id: str
    total: int
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_type: Dict[str, int] = Field(default_factory=dict)


class ComplexityAnalysisRequest(BaseModel):
    """Configurable thresholds for cyclomatic complexity and function length analysis."""
    complexity_warning_threshold: int = Field(default=10, ge=1, description="Cyclomatic complexity threshold for Medium severity")
    complexity_critical_threshold: int = Field(default=15, ge=1, description="Cyclomatic complexity threshold for High/Critical severity")
    long_function_warning_lines: int = Field(default=50, ge=1, description="Function line count threshold for Medium severity")
    long_function_critical_lines: int = Field(default=100, ge=1, description="Function line count threshold for High severity")


class ComplexityAnalysisResult(BaseModel):
    """Response returned upon completing complexity analysis."""
    project_id: str
    findings_count: int
    message: str
    findings: List[FindingResponse]


class DeadCodeAnalysisRequest(BaseModel):
    """Optional configuration for dead-code analysis."""
    entry_points: Optional[List[str]] = Field(default=None, description="Optional custom list of entry point relative file paths")


class DeadCodeAnalysisResult(BaseModel):
    """Response returned upon completing dead-code candidate analysis."""
    project_id: str
    entry_points: List[str]
    unreachable_files_count: int
    findings_count: int
    message: str
    findings: List[FindingResponse]


class ArchitectureAnalysisRequest(BaseModel):
    """Configuration thresholds for architecture cycle and god-module analysis."""
    total_degree_threshold: int = Field(default=8, ge=2, description="Total degree (fan-in + fan-out) threshold to flag god modules")
    betweenness_threshold: float = Field(default=0.20, ge=0.0, le=1.0, description="Betweenness centrality threshold to flag bottlenecks")


class ArchitectureAnalysisResult(BaseModel):
    """Response returned upon completing architecture analysis."""
    project_id: str
    cycles_count: int
    god_modules_count: int
    total_findings: int
    message: str
    findings: List[FindingResponse]


class SecurityAnalysisRequest(BaseModel):
    """Configuration for static vulnerability and security analysis."""
    enable_bandit: bool = Field(default=True, description="Enable Bandit vulnerability scanner")
    enable_semgrep: bool = Field(default=True, description="Enable Semgrep scanner if available")


class SecurityAnalysisResult(BaseModel):
    """Response returned upon completing security vulnerability analysis."""
    project_id: str
    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    info_count: int
    message: str
    findings: List[FindingResponse]


# --- Endpoints ---

@router.post(
    "/{project_id}/analyze/complexity",
    response_model=ComplexityAnalysisResult,
    summary="Run McCabe cyclomatic complexity and long-function analysis",
    description="Analyzes all Python files in the project for high cyclomatic complexity and overly long functions.",
)
async def analyze_project_complexity(
    project_id: str,
    request: Optional[ComplexityAnalysisRequest] = None,
    db: Session = Depends(get_db),
) -> ComplexityAnalysisResult:
    """Execute McCabe cyclomatic complexity analysis and persist findings."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )

    project_root = Path(project.path)
    if not project_root.exists() or not project_root.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project directory '{project.path}' does not exist on disk.",
        )

    # Configure thresholds if provided
    cfg = request or ComplexityAnalysisRequest()
    thresholds = ComplexityThresholds(
        complexity_warning_threshold=cfg.complexity_warning_threshold,
        complexity_critical_threshold=cfg.complexity_critical_threshold,
        long_function_warning_lines=cfg.long_function_warning_lines,
        long_function_critical_lines=cfg.long_function_critical_lines,
    )

    analyzer = ComplexityAnalyzer(thresholds=thresholds)
    raw_findings = analyzer.analyze_project(project_root=project_root, project_id=project_id)

    # Persist findings to database, replacing previous complexity findings
    saved_records = crud.save_findings(
        db=db,
        project_id=project_id,
        findings_data=raw_findings,
        replace_type="complexity",
    )

    return ComplexityAnalysisResult(
        project_id=project_id,
        findings_count=len(saved_records),
        message=f"Complexity analysis completed: {len(saved_records)} findings identified.",
        findings=[FindingResponse.model_validate(f) for f in saved_records],
    )


@router.post(
    "/{project_id}/analyze/dead-code",
    response_model=DeadCodeAnalysisResult,
    summary="Run dead-code candidate analysis",
    description="Traverses NetworkX dependency graph via BFS/DFS from entry points and cross-checks with Vulture.",
)
async def analyze_project_dead_code(
    project_id: str,
    request: Optional[DeadCodeAnalysisRequest] = None,
    db: Session = Depends(get_db),
) -> DeadCodeAnalysisResult:
    """Execute dead-code candidate analysis using graph reachability and Vulture."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )

    project_root = Path(project.path)
    if not project_root.exists() or not project_root.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project directory '{project.path}' does not exist on disk.",
        )

    req_entries = request.entry_points if request else None
    analyzer = DeadCodeAnalyzer(entry_points=req_entries)
    raw_findings = analyzer.analyze_project(project_root=project_root, project_id=project_id)

    # Persist findings to database, replacing previous dead_code findings
    saved_records = crud.save_findings(
        db=db,
        project_id=project_id,
        findings_data=raw_findings,
        replace_type="dead_code",
    )

    unreachable_count = sum(1 for f in saved_records if "Unreachable file" in f.title)

    return DeadCodeAnalysisResult(
        project_id=project_id,
        entry_points=analyzer.last_entry_points,
        unreachable_files_count=unreachable_count,
        findings_count=len(saved_records),
        message=f"Dead-code analysis completed: {len(saved_records)} candidate findings identified ({unreachable_count} unreachable files).",
        findings=[FindingResponse.model_validate(f) for f in saved_records],
    )


@router.post(
    "/{project_id}/analyze/architecture",
    response_model=ArchitectureAnalysisResult,
    summary="Run circular dependencies (Tarjan SCC) and god-module coupling analysis",
    description="Analyzes the dependency graph using Tarjan's SCC algorithm for import cycles, and degree/betweenness centrality for god modules.",
)
async def analyze_project_architecture(
    project_id: str,
    request: Optional[ArchitectureAnalysisRequest] = None,
    db: Session = Depends(get_db),
) -> ArchitectureAnalysisResult:
    """Execute circular dependency and coupling/god-module analysis."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )

    project_root = Path(project.path)
    if not project_root.exists() or not project_root.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project directory '{project.path}' does not exist on disk.",
        )

    cfg = request or ArchitectureAnalysisRequest()
    analyzer = ArchitectureAnalyzer(
        total_degree_threshold=cfg.total_degree_threshold,
        betweenness_threshold=cfg.betweenness_threshold,
    )
    raw_findings = analyzer.analyze_project(project_root=project_root, project_id=project_id)

    # Separate cycles and coupling findings for clear replacement in DB
    cycle_findings = [f for f in raw_findings if f["type"] == "cycle"]
    coupling_findings = [f for f in raw_findings if f["type"] == "coupling"]

    saved_cycles = crud.save_findings(db, project_id, cycle_findings, replace_type="cycle")
    saved_coupling = crud.save_findings(db, project_id, coupling_findings, replace_type="coupling")
    all_saved = saved_cycles + saved_coupling

    return ArchitectureAnalysisResult(
        project_id=project_id,
        cycles_count=len(saved_cycles),
        god_modules_count=len(saved_coupling),
        total_findings=len(all_saved),
        message=(
            f"Architecture analysis completed: {len(saved_cycles)} circular dependencies, "
            f"{len(saved_coupling)} god modules identified."
        ),
        findings=[FindingResponse.model_validate(f) for f in all_saved],
    )


@router.post(
    "/{project_id}/analyze/security",
    response_model=SecurityAnalysisResult,
    summary="Run security vulnerability and secret detection analysis",
    description=(
        "Executes static security analysis combining Bandit, Semgrep (if available), "
        "and custom AST rules for secrets, eval/exec, subprocess shell=True, SQL injection, "
        "and insecure deserialization. Normalizes severities and labels all findings as potential."
    ),
)
async def analyze_project_security(
    project_id: str,
    request: Optional[SecurityAnalysisRequest] = None,
    db: Session = Depends(get_db),
) -> SecurityAnalysisResult:
    """Execute static security analysis and persist security findings."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )

    project_root = Path(project.path)
    if not project_root.exists() or not project_root.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project directory '{project.path}' does not exist on disk.",
        )

    cfg = request or SecurityAnalysisRequest()
    analyzer = SecurityAnalyzer(
        enable_bandit=cfg.enable_bandit,
        enable_semgrep=cfg.enable_semgrep,
    )
    raw_findings = analyzer.analyze_project(project_root=project_root, project_id=project_id)

    # Persist security findings replacing previous security findings
    saved_findings = crud.save_findings(db, project_id, raw_findings, replace_type="security")

    # Tally counts by severity
    critical_count = sum(1 for f in saved_findings if f.severity == "Critical")
    high_count = sum(1 for f in saved_findings if f.severity == "High")
    medium_count = sum(1 for f in saved_findings if f.severity == "Medium")
    low_count = sum(1 for f in saved_findings if f.severity == "Low")
    info_count = sum(1 for f in saved_findings if f.severity == "Info")

    return SecurityAnalysisResult(
        project_id=project_id,
        total_findings=len(saved_findings),
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        info_count=info_count,
        message=(
            f"Security analysis completed: {len(saved_findings)} potential security findings identified "
            f"({critical_count} Critical, {high_count} High, {medium_count} Medium, {low_count} Low)."
        ),
        findings=[FindingResponse.model_validate(f) for f in saved_findings],
    )


@router.get(
    "/{project_id}/findings",
    response_model=FindingsListResponse,
    summary="List static analysis findings",
    description="Retrieve findings for a project with optional filtering by type, severity, or file path.",
)
async def list_findings(
    project_id: str,
    type: Optional[str] = Query(None, description="Filter by finding type: complexity, dead_code, cycle, security"),
    severity: Optional[str] = Query(None, description="Filter by severity: Critical, High, Medium, Low, Info"),
    file: Optional[str] = Query(None, description="Filter by relative file path"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Max records to return"),
    offset: Optional[int] = Query(None, ge=0, description="Records offset for pagination"),
    db: Session = Depends(get_db),
) -> FindingsListResponse:
    """Query findings stored in database for the given project."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )

    findings, total_count = crud.get_project_findings(
        db=db,
        project_id=project_id,
        finding_type=type,
        severity=severity,
        file_path=file,
        limit=limit,
        offset=offset,
    )

    return FindingsListResponse(
        project_id=project_id,
        total=total_count,
        count=len(findings),
        findings=[FindingResponse.model_validate(f) for f in findings],
    )


@router.get(
    "/{project_id}/findings/summary",
    response_model=FindingsSummaryResponse,
    summary="Get findings aggregate summary",
    description="Returns total findings counts and breakdowns grouped by severity and category type.",
)
async def get_findings_summary(
    project_id: str,
    db: Session = Depends(get_db),
) -> FindingsSummaryResponse:
    """Fetch findings summary statistics for a project."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )

    summary_data = crud.get_findings_summary(db=db, project_id=project_id)
    return FindingsSummaryResponse(
        project_id=project_id,
        total=summary_data["total"],
        by_severity=summary_data["by_severity"],
        by_type=summary_data["by_type"],
    )


@router.delete(
    "/{project_id}/findings",
    status_code=status.HTTP_200_OK,
    summary="Delete findings for a project",
)
async def clear_findings(
    project_id: str,
    type: Optional[str] = Query(None, description="Optional finding type to delete"),
    db: Session = Depends(get_db),
):
    """Delete findings for a project, optionally filtered by type."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )

    deleted_count = crud.delete_project_findings(db, project_id, finding_type=type)
    return {"message": f"Successfully deleted {deleted_count} findings for project '{project_id}'."}
