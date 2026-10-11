"""
AnalysisState: Typed shared state for the LangGraph agent workflow.
Maintains continuous pipeline telemetry, step progress, intermediate AST entities,
static findings, vector indexing metrics, and hierarchical documentation.
"""

from typing import Any, Dict, List, Optional, TypedDict


class AnalysisState(TypedDict, total=False):
    """
    Typed shared state passed through the LangGraph StateGraph nodes.
    Each node receives this state, executes its deterministic analysis or enrichment,
    and returns a state update dictionary.
    """
    # Core project identifiers
    project_id: str
    project_path: str
    project_name: str
    run_id: Optional[int]

    # Pipeline lifecycle & telemetry
    status: str  # "pending", "running", "completed", "failed"
    step: str  # e.g. "Scanning files", "Parsing AST", "Generating documentation"
    progress_percent: int  # 0 to 100
    current_activity: str
    error_message: Optional[str]
    logs: List[str]

    # Step 1: Repository Ingestion & Scanning
    total_files: int
    total_lines: int
    scanned_files: List[Dict[str, Any]]
    languages: Dict[str, int]

    # Step 2: AST Parsing
    parsed_files_count: int
    unparsable_files: List[Dict[str, str]]  # Files that failed parsing: [{"file": ..., "error": ...}]
    entities_count: int

    # Step 3: Architecture Graph
    graph_nodes_count: int
    graph_edges_count: int
    graph_density: float

    # Step 4: Deterministic Static Analysis
    findings: List[Dict[str, Any]]
    findings_count: int
    critical_high_count: int
    needs_context_enrichment: bool

    # Step 5: Vector Store (RAG) Indexing
    indexed_chunks_count: int

    # Step 6: Finding Context Enrichment
    enriched_findings_count: int
    insufficient_evidence_count: int

    # Step 7: Hierarchical Documentation Generation
    file_summaries: List[Dict[str, Any]]
    module_summaries: List[Dict[str, Any]]
    repo_overview: Dict[str, Any]
    markdown_documentation: str
    docs_saved_path: Optional[str]
