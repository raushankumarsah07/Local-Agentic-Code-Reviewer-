import asyncio
import concurrent.futures
import json
from pathlib import Path
from typing import Any, Dict, List

from app.agent.docs import (
    export_markdown_documentation,
    generate_file_summary,
    generate_module_summaries,
    generate_repository_overview,
    save_markdown_documentation,
)
from app.agent.state import AnalysisState
from app.analysis.architecture import ArchitectureAnalyzer
from app.analysis.complexity import ComplexityAnalyzer, ComplexityThresholds
from app.analysis.dead_code import DeadCodeAnalyzer
from app.analysis.security import SecurityAnalyzer
from app.db import crud
from app.db.session import SessionLocal
from app.graph.builder import DependencyGraphBuilder
from app.ingestion.scanner import scan_repository
from app.parsing.base import ParsedFile
from app.parsing.python_parser import PythonParser
from app.rag.chunker import chunk_repository
from app.rag.knowledge_base import KnowledgeBaseManager
from app.rag.retriever import RepositoryRetriever
from app.rag.vector_store import ChromaStoreManager


def _run_sync(coro):
    """Safely execute an async coroutine from synchronous step functions."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


def scan_step(state: AnalysisState) -> Dict[str, Any]:
    """
    Step 1: Ingestion & Scanning.
    Discovers all project files, line counts, sizes, and programming languages.
    """
    project_id = state["project_id"]
    project_path = Path(state["project_path"])

    summary = scan_repository(project_path, project_id)
    files_payload = [
        {
            "path": f.path,
            "language": f.language,
            "size_bytes": f.size_bytes,
            "line_count": f.line_count,
        }
        for f in summary.files
    ]

    with SessionLocal() as db:
        crud.save_project_files(db=db, project_id=project_id, files_data=files_payload)
        project = crud.get_project(db, project_id)
        if project:
            project.total_files = summary.total_files
            project.total_lines = summary.total_lines
            project.total_size_bytes = summary.total_size_bytes
            db.commit()

    log_entry = f"Scanned {summary.total_files} files ({summary.total_lines} lines across {len(summary.languages)} languages)"
    return {
        "step": "Scanning files",
        "progress_percent": 15,
        "current_activity": log_entry,
        "total_files": summary.total_files,
        "total_lines": summary.total_lines,
        "scanned_files": files_payload,
        "languages": summary.languages,
        "logs": state.get("logs", []) + [log_entry],
    }


def parse_step(state: AnalysisState) -> Dict[str, Any]:
    """
    Step 2: AST Parsing & Entity Extraction.
    Parses Python source files using PythonParser.
    Conditional rule: If an individual file fails to parse, logs the error and continues.
    """
    project_id = state["project_id"]
    project_path = Path(state["project_path"])
    parser = PythonParser()

    parsed_count = 0
    unparsable_files: List[Dict[str, str]] = []
    entities_to_save: List[Dict[str, Any]] = []

    # Filter for Python files
    scanned_files = state.get("scanned_files", [])
    py_files = [f for f in scanned_files if f.get("language") == "Python"]

    # If state didn't have scanned_files, scan disk
    if not py_files and project_path.exists():
        py_files = [{"path": p.relative_to(project_path).as_posix()} for p in project_path.rglob("*.py")]

    for f_info in py_files:
        rel_path = f_info["path"]
        target_file = project_path / rel_path

        try:
            parsed: ParsedFile = parser.parse_file(target_file, project_root=project_path)
            if not parsed.is_parsable:
                unparsable_files.append({
                    "file": rel_path,
                    "error": parsed.error_message or "Syntax parsing failed",
                })
                continue

            parsed_count += 1

            # Extract classes
            for cls in parsed.classes:
                entities_to_save.append({
                    "file_path": rel_path,
                    "entity_type": "class",
                    "name": cls.name,
                    "parent_name": None,
                    "start_line": cls.start_line,
                    "end_line": cls.end_line,
                    "details": json.dumps({"bases": cls.bases, "docstring": cls.docstring}),
                })
                for m in cls.methods:
                    entities_to_save.append({
                        "file_path": rel_path,
                        "entity_type": "method",
                        "name": m.name,
                        "parent_name": cls.name,
                        "start_line": m.start_line,
                        "end_line": m.end_line,
                        "details": json.dumps({"params": m.params, "docstring": m.docstring}),
                    })

            # Extract functions
            for fn in parsed.functions:
                entities_to_save.append({
                    "file_path": rel_path,
                    "entity_type": "function",
                    "name": fn.name,
                    "parent_name": None,
                    "start_line": fn.start_line,
                    "end_line": fn.end_line,
                    "details": json.dumps({"params": fn.params, "docstring": fn.docstring}),
                })

            # Extract imports
            for imp in parsed.imports:
                entities_to_save.append({
                    "file_path": rel_path,
                    "entity_type": "import",
                    "name": imp.imported_name,
                    "parent_name": None,
                    "start_line": imp.line_number,
                    "end_line": imp.line_number,
                    "details": json.dumps({"module": imp.module, "alias": imp.alias}),
                })

        except Exception as e:
            # Tolerant error handling: log and continue
            unparsable_files.append({"file": rel_path, "error": str(e)})

    # Persist code entities in DB
    with SessionLocal() as db:
        crud.save_code_entities(db=db, project_id=project_id, entities_data=entities_to_save)

    log_entry = f"Parsed {parsed_count} Python files ({len(entities_to_save)} AST entities extracted, {len(unparsable_files)} unparsable)"
    return {
        "step": "Parsing AST",
        "progress_percent": 30,
        "current_activity": log_entry,
        "parsed_files_count": parsed_count,
        "unparsable_files": unparsable_files,
        "entities_count": len(entities_to_save),
        "logs": state.get("logs", []) + [log_entry],
    }


def build_graph_step(state: AnalysisState) -> Dict[str, Any]:
    """
    Step 3: Dependency Graph Construction.
    Builds NetworkX directed architecture graph and computes degree metrics.
    """
    project_id = state["project_id"]
    project_path = Path(state["project_path"])

    builder = DependencyGraphBuilder(project_root=project_path, project_id=project_id)
    graph_data = builder.export_json(include_external=True)

    with SessionLocal() as db:
        edges_to_save = [
            {
                "source": e.source,
                "target": e.target,
                "edge_type": e.edge_type,
                "is_external": e.is_external,
                "imported_symbols": e.imported_symbols,
                "line_number": e.line_number,
            }
            for e in graph_data.edges
        ]
        crud.save_graph_edges(db=db, project_id=project_id, edges_data=edges_to_save)

    node_count = len(graph_data.nodes)
    edge_count = len(graph_data.edges)
    density = (edge_count / (node_count * (node_count - 1))) if node_count > 1 else 0.0
    log_entry = f"Built architecture graph with {node_count} nodes and {edge_count} dependency edges"

    return {
        "step": "Building dependency graph",
        "progress_percent": 45,
        "current_activity": log_entry,
        "graph_nodes_count": node_count,
        "graph_edges_count": edge_count,
        "graph_density": round(density, 4),
        "logs": state.get("logs", []) + [log_entry],
    }


def run_static_checks_step(state: AnalysisState) -> Dict[str, Any]:
    """
    Step 4: Deterministic Static Analysis.
    Runs complexity, dead code, architectural cycles/god-modules, and security checks.
    Evaluates findings to determine if high/critical issues require context enrichment.
    """
    project_id = state["project_id"]
    project_path = Path(state["project_path"])

    # 1. Complexity
    c_analyzer = ComplexityAnalyzer(thresholds=ComplexityThresholds())
    c_findings = c_analyzer.analyze_project(project_root=project_path, project_id=project_id)

    # 2. Dead Code
    d_analyzer = DeadCodeAnalyzer()
    d_findings = d_analyzer.analyze_project(project_root=project_path, project_id=project_id)

    # 3. Architecture (Cycles & God Modules)
    a_analyzer = ArchitectureAnalyzer()
    a_findings = a_analyzer.analyze_project(project_root=project_path, project_id=project_id)
    cycle_findings = [f for f in a_findings if f["type"] == "cycle"]
    coupling_findings = [f for f in a_findings if f["type"] == "coupling"]

    # 4. Security (Bandit & custom AST rules)
    s_analyzer = SecurityAnalyzer(enable_bandit=True, enable_semgrep=False)
    s_findings = s_analyzer.analyze_project(project_root=project_path, project_id=project_id)

    # Persist all findings in DB
    all_findings = c_findings + d_findings + a_findings + s_findings
    with SessionLocal() as db:
        crud.save_findings(db, project_id, c_findings, replace_type="complexity")
        crud.save_findings(db, project_id, d_findings, replace_type="dead_code")
        crud.save_findings(db, project_id, cycle_findings, replace_type="cycle")
        crud.save_findings(db, project_id, coupling_findings, replace_type="coupling")
        crud.save_findings(db, project_id, s_findings, replace_type="security")

    critical_high = [f for f in all_findings if f.get("severity") in ("Critical", "High")]
    log_entry = (
        f"Completed static checks: {len(all_findings)} total findings "
        f"({len(critical_high)} Critical/High, {len(c_findings)} complexity, "
        f"{len(d_findings)} dead-code, {len(cycle_findings)} cycles, {len(s_findings)} security)"
    )

    return {
        "step": "Running static checks",
        "progress_percent": 60,
        "current_activity": log_entry,
        "findings": all_findings,
        "findings_count": len(all_findings),
        "critical_high_count": len(critical_high),
        "needs_context_enrichment": len(critical_high) > 0,
        "logs": state.get("logs", []) + [log_entry],
    }


def index_code_step(state: AnalysisState) -> Dict[str, Any]:
    """
    Step 5: Vector Store (RAG) Indexing.
    Chunks all repository code with AST boundaries and indexes into ChromaDB.
    """
    project_id = state["project_id"]
    project_path = Path(state["project_path"])

    chunks = chunk_repository(project_path, project_id=project_id)
    store_mgr = ChromaStoreManager()
    indexed_count = _run_sync(store_mgr.index_chunks(project_id, chunks))

    log_entry = f"Indexed {indexed_count} AST-aware code chunks in ChromaDB vector store"
    return {
        "step": "Indexing code in vector store",
        "progress_percent": 75,
        "current_activity": log_entry,
        "indexed_chunks_count": indexed_count,
        "logs": state.get("logs", []) + [log_entry],
    }


def check_findings_enrichment_needed(state: AnalysisState) -> str:
    """
    Conditional Edge Evaluator:
    If high or critical findings exist, routes to 'enrich_findings' to retrieve
    extra architectural and knowledge-base context. Otherwise routes to 'review_findings'.
    """
    if state.get("critical_high_count", 0) > 0:
        return "enrich_findings"
    return "review_findings"


def enrich_findings_step(state: AnalysisState) -> Dict[str, Any]:
    """
    Conditional Step 6A: Finding Context Enrichment.
    Triggered when High/Critical findings exist. Retrieves extra context before asking LLM.
    Conditional rule: If retrieved context is empty, reports 'insufficient evidence' instead of guessing.
    """
    project_id = state["project_id"]
    findings = state.get("findings", [])
    critical_high = [f for f in findings if f.get("severity") in ("Critical", "High")]

    store_mgr = ChromaStoreManager()
    retriever = RepositoryRetriever(store_manager=store_mgr)
    kb_mgr = KnowledgeBaseManager(store_manager=store_mgr)

    enriched_count = 0
    insufficient_evidence_count = 0

    with SessionLocal() as db:
        # Retrieve stored finding records
        db_findings, _ = crud.get_project_findings(db, project_id)
        db_findings_map = {f.title: f for f in db_findings}

        for finding in critical_high:
            title = finding.get("title", "")
            finding_file = finding.get("file", "")
            query = f"{title} in {finding_file}"

            retrieval_res = _run_sync(retriever.retrieve(project_id=project_id, query=query, top_k=3, db=db))
            kb_chunks = _run_sync(kb_mgr.query_knowledge_base(query=title, top_k=2))

            db_record = db_findings_map.get(title)
            if not db_record:
                continue

            # Spec: empty retrieval -> report 'insufficient evidence' instead of guessing
            if not retrieval_res.all_chunks:
                insufficient_evidence_count += 1
                explanation_payload = {
                    "problem": title,
                    "risk": "Insufficient evidence: No matching context found in repository to verify risk.",
                    "recommended_fix": "Perform manual code inspection.",
                    "confidence_note": "insufficient_evidence",
                }
                crud.save_finding_explanation(
                    db=db,
                    finding_id=db_record.id,
                    model_name="rule_based_fallback",
                    prompt_version="v1.0",
                    explanation_json=json.dumps(explanation_payload),
                    status="insufficient_evidence",
                )
            else:
                enriched_count += 1
                evidence_notes = [f"Retrieved {len(retrieval_res.all_chunks)} code chunk(s)"]
                if kb_chunks:
                    evidence_notes.append(f"matched KB guide: {kb_chunks[0].doc_title}")

                explanation_payload = {
                    "problem": title,
                    "risk": f"Potential security/architectural risk flagged in {finding_file}:{finding.get('start_line', 0)}.",
                    "recommended_fix": (
                        kb_chunks[0].content[:200] if kb_chunks
                        else "Review and validate security controls or modularity."
                    ),
                    "confidence_note": f"Enriched with context ({', '.join(evidence_notes)})",
                }
                crud.save_finding_explanation(
                    db=db,
                    finding_id=db_record.id,
                    model_name="rag_enriched_explainer",
                    explanation_json=json.dumps(explanation_payload),
                    status="success",
                )

    log_entry = (
        f"Enriched {enriched_count} Critical/High finding(s) with call-graph & KB context "
        f"({insufficient_evidence_count} flagged as insufficient evidence)"
    )
    return {
        "step": "Enriching security findings",
        "progress_percent": 85,
        "current_activity": log_entry,
        "enriched_findings_count": enriched_count,
        "insufficient_evidence_count": insufficient_evidence_count,
        "logs": state.get("logs", []) + [log_entry],
    }


def review_findings_step(state: AnalysisState) -> Dict[str, Any]:
    """
    Step 6B: Findings Review & Aggregation.
    Finalizes findings statistics for documentation synthesis.
    """
    findings = state.get("findings", [])
    log_entry = f"Reviewed {len(findings)} findings across all static analysis categories"
    return {
        "step": "Reviewing findings summary",
        "progress_percent": 90,
        "current_activity": log_entry,
        "logs": state.get("logs", []) + [log_entry],
    }


def generate_docs_step(state: AnalysisState) -> Dict[str, Any]:
    """
    Step 7: Documentation Generator (Map-Reduce Style).
    Map: per-file summaries.
    Reduce: module summaries.
    Reduce: repository overview.
    Export: full GitHub Markdown document written to disk and DB.
    """
    project_id = state["project_id"]
    project_path = Path(state["project_path"])
    project_name = state.get("project_name", project_path.name)

    # 1. Map: Per-file summaries
    with SessionLocal() as db:
        files, _ = crud.get_project_files(db=db, project_id=project_id)
        all_entities = crud.get_project_entities(db=db, project_id=project_id)
        findings_summary = crud.get_findings_summary(db=db, project_id=project_id)

    entities_by_file: Dict[str, List[Dict[str, Any]]] = {}
    for ent in all_entities:
        entities_by_file.setdefault(ent.file_path, []).append({
            "name": ent.name,
            "entity_type": ent.entity_type,
            "start_line": ent.start_line,
            "end_line": ent.end_line,
        })

    file_summaries: List[Dict[str, Any]] = []
    for f in files:
        f_rec = {"path": f.path, "language": f.language, "line_count": f.line_count, "size_bytes": f.size_bytes}
        f_sum = generate_file_summary(f_rec, entities_by_file.get(f.path, []))
        file_summaries.append(f_sum)

    # 2. Reduce: Module summaries
    module_summaries = generate_module_summaries(file_summaries)

    # 3. Reduce: Repository overview
    graph_metrics = {
        "nodes_count": state.get("graph_nodes_count", len(files)),
        "edges_count": state.get("graph_edges_count", 0),
    }
    repo_overview = generate_repository_overview(
        project_name=project_name,
        file_summaries=file_summaries,
        module_summaries=module_summaries,
        graph_metrics=graph_metrics,
        findings_summary=findings_summary,
    )

    # 4. Export Markdown documentation
    markdown_doc = export_markdown_documentation(
        repo_overview=repo_overview,
        module_summaries=module_summaries,
        file_summaries=file_summaries,
        findings_summary=findings_summary,
    )

    # Write to disk
    saved_doc_path = save_markdown_documentation(project_path, markdown_doc)

    # Save to database
    with SessionLocal() as db:
        summary_payload = json.dumps({
            "overview": repo_overview,
            "modules": module_summaries,
            "files": file_summaries,
        })
        crud.save_project_doc(
            db=db,
            project_id=project_id,
            overview_md=markdown_doc,
            summary_data=summary_payload,
        )

    log_entry = f"Generated hierarchical repository documentation and exported to {saved_doc_path.name}"
    return {
        "step": "Generating documentation",
        "progress_percent": 100,
        "current_activity": log_entry,
        "status": "completed",
        "file_summaries": file_summaries,
        "module_summaries": module_summaries,
        "repo_overview": repo_overview,
        "markdown_documentation": markdown_doc,
        "docs_saved_path": str(saved_doc_path),
        "logs": state.get("logs", []) + [log_entry],
    }
