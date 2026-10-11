"""
Tests for Phase 10: Agent Workflow (LangGraph StateGraph & Documentation Generator).
Verifies:
1. Every step exists as a plain, testable Python function.
2. Robust parsing: unparsable files are logged and skipped without failing.
3. LangGraph StateGraph compiles and runs end-to-end.
4. Conditional edges: high/critical findings trigger context enrichment.
5. Empty retrieval reports 'insufficient evidence' instead of guessing.
6. Hierarchical map-reduce documentation generator and Markdown export.
7. REST API endpoints: POST /projects/{id}/analyze, GET /projects/{id}/status, GET /projects/{id}/docs.
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.agent.docs import (
    export_markdown_documentation,
    generate_file_summary,
    generate_module_summaries,
    generate_repository_overview,
)
from app.agent.runner import execute_analysis_sync, get_pipeline_status
from app.agent.state import AnalysisState
from app.agent.steps import (
    build_graph_step,
    check_findings_enrichment_needed,
    enrich_findings_step,
    generate_docs_step,
    index_code_step,
    parse_step,
    review_findings_step,
    run_static_checks_step,
    scan_step,
)
from app.agent.workflow import create_analysis_workflow
from app.db import crud
from app.db.session import SessionLocal
from app.main import app


@pytest.fixture
def test_project(tmp_path):
    """Creates a temporary sample repository for testing the agent workflow."""
    repo_dir = tmp_path / "sample_app"
    repo_dir.mkdir(parents=True)

    # 1. Main entry point
    (repo_dir / "main.py").write_text(
        '"""Main application entry point."""\n\n'
        'from service import calculate_total\n\n'
        'def main():\n'
        '    print("Total:", calculate_total(10, 5))\n\n'
        'if __name__ == "__main__":\n'
        '    main()\n',
        encoding="utf-8",
    )

    # 2. Service module with function and class
    (repo_dir / "service.py").write_text(
        '"""Business logic calculation service."""\n\n'
        'class Calculator:\n'
        '    """Arithmetic processor."""\n'
        '    def add(self, a: int, b: int) -> int:\n'
        '        return a + b\n\n'
        'def calculate_total(x: int, y: int) -> int:\n'
        '    calc = Calculator()\n'
        '    return calc.add(x, y)\n',
        encoding="utf-8",
    )

    # 3. Deliberately broken syntax file to verify fault tolerance
    (repo_dir / "broken_syntax.py").write_text(
        'def broken_func(:\n    syntax error here\n',
        encoding="utf-8",
    )

    proj_id = "test_agent_proj_01"
    with SessionLocal() as db:
        crud.delete_project(db, proj_id)
        project = crud.create_project(
            db=db,
            project_id=proj_id,
            name="sample_app",
            path=str(repo_dir),
            total_files=3,
            total_lines=20,
            total_size_bytes=400,
        )

    yield proj_id, repo_dir

    with SessionLocal() as db:
        crud.delete_project(db, proj_id)


def test_plain_python_steps_exist_and_run(test_project):
    """Confirm every step exists as a plain, testable Python function."""
    proj_id, repo_dir = test_project

    state: AnalysisState = {
        "project_id": proj_id,
        "project_path": str(repo_dir),
        "project_name": "sample_app",
        "status": "running",
        "step": "init",
        "progress_percent": 0,
        "logs": [],
    }

    # 1. scan_step
    scan_res = scan_step(state)
    assert scan_res["total_files"] >= 2
    assert "Scanning files" in scan_res["step"]
    state.update(scan_res)

    # 2. parse_step (tolerant of broken_syntax.py)
    parse_res = parse_step(state)
    assert parse_res["parsed_files_count"] >= 2
    assert len(parse_res["unparsable_files"]) == 1  # broken_syntax.py was gracefully caught
    assert parse_res["unparsable_files"][0]["file"] == "broken_syntax.py"
    state.update(parse_res)

    # 3. build_graph_step
    graph_res = build_graph_step(state)
    assert graph_res["graph_nodes_count"] >= 2
    state.update(graph_res)

    # 4. run_static_checks_step
    checks_res = run_static_checks_step(state)
    assert "findings" in checks_res
    assert isinstance(checks_res["findings_count"], int)
    state.update(checks_res)

    # 5. index_code_step
    idx_res = index_code_step(state)
    assert idx_res["indexed_chunks_count"] >= 2
    state.update(idx_res)

    # 6. review_findings_step
    review_res = review_findings_step(state)
    assert "Reviewing findings" in review_res["step"]
    state.update(review_res)

    # 7. generate_docs_step
    doc_res = generate_docs_step(state)
    assert doc_res["status"] == "completed"
    assert "markdown_documentation" in doc_res
    assert len(doc_res["file_summaries"]) >= 2
    assert len(doc_res["module_summaries"]) >= 1


def test_conditional_edges_routing(test_project):
    """Test conditional edge evaluator: routes to enrichment when High/Critical findings exist."""
    state_with_critical: AnalysisState = {"critical_high_count": 2}
    assert check_findings_enrichment_needed(state_with_critical) == "enrich_findings"

    state_without_critical: AnalysisState = {"critical_high_count": 0}
    assert check_findings_enrichment_needed(state_without_critical) == "review_findings"


def test_empty_retrieval_reports_insufficient_evidence(tmp_path):
    """Verify empty retrieval reports 'insufficient evidence' instead of guessing."""
    proj_id = "test_empty_ev_01"
    repo_dir = tmp_path / "empty_repo"
    repo_dir.mkdir(parents=True)
    (repo_dir / "simple.py").write_text("x = 1\n", encoding="utf-8")

    with SessionLocal() as db:
        crud.delete_project(db, proj_id)
        crud.create_project(db, proj_id, "empty_repo", str(repo_dir))
        # Create a synthetic high finding that has zero matching symbols
        saved = crud.save_findings(
            db=db,
            project_id=proj_id,
            findings_data=[{
                "type": "security",
                "severity": "High",
                "title": "Quantum Entanglement Vulnerability (Nonexistent)",
                "file": "nonexistent_file.py",
                "start_line": 99,
                "end_line": 100,
                "source_tool": "test",
                "evidence_snippet": "xyz",
            }],
        )
        finding_id = saved[0].id

    state: AnalysisState = {
        "project_id": proj_id,
        "project_path": str(repo_dir),
        "findings": [{
            "severity": "High",
            "title": "Quantum Entanglement Vulnerability (Nonexistent)",
            "file": "nonexistent_file.py",
            "start_line": 99,
        }],
    }

    res = enrich_findings_step(state)
    assert res["insufficient_evidence_count"] >= 1

    with SessionLocal() as db:
        explanation = crud.get_finding_explanation(db, finding_id)
        assert explanation is not None
        assert explanation.status == "insufficient_evidence"
        parsed = json.loads(explanation.explanation)
        assert "Insufficient evidence" in parsed["risk"]
        crud.delete_project(db, proj_id)


def test_map_reduce_documentation_generator():
    """Verify Map-Reduce documentation generator generates structured Markdown."""
    file_record = {"path": "calculator.py", "language": "Python", "line_count": 50, "size_bytes": 1200}
    entities = [
        {"entity_type": "class", "name": "BasicCalculator", "start_line": 5, "end_line": 30},
        {"entity_type": "function", "name": "add_numbers", "start_line": 32, "end_line": 40},
        {"entity_type": "import", "name": "math", "start_line": 1, "end_line": 1},
    ]

    # Map step
    f_sum = generate_file_summary(file_record, entities)
    assert f_sum["file_path"] == "calculator.py"
    assert f_sum["classes_count"] == 1
    assert f_sum["functions_count"] == 1
    assert "math" in f_sum["imports"]

    # Reduce step
    mod_summaries = generate_module_summaries([f_sum])
    assert len(mod_summaries) == 1
    assert mod_summaries[0]["module_name"] == "root"

    # Reduce overview
    overview = generate_repository_overview("TestCalc", [f_sum], mod_summaries)
    assert overview["total_files"] == 1
    assert overview["total_classes"] == 1

    # Markdown export
    md = export_markdown_documentation(overview, mod_summaries, [f_sum])
    assert "# Architecture & Repository Documentation: TestCalc" in md
    assert "BasicCalculator" in md
    assert "add_numbers" in md


def test_langgraph_full_workflow_execution(test_project):
    """Test full LangGraph StateGraph execution end-to-end."""
    proj_id, _ = test_project

    final_state = execute_analysis_sync(proj_id)
    assert final_state["status"] == "completed"
    assert final_state["progress_percent"] == 100
    assert final_state["parsed_files_count"] >= 2
    assert final_state["graph_nodes_count"] >= 2
    assert "markdown_documentation" in final_state

    # Check database status
    status = get_pipeline_status(proj_id)
    assert status["status"] == "completed"
    assert status["progress_percent"] == 100

    # Check documentation record in DB
    with SessionLocal() as db:
        doc = crud.get_project_doc(db, proj_id)
        assert doc is not None
        assert "# Architecture & Repository Documentation" in doc.overview_md


def test_api_analyze_and_status_endpoints(test_project):
    """Test POST /projects/{id}/analyze and GET /projects/{id}/status endpoints."""
    proj_id, _ = test_project
    client = TestClient(app)

    # 1. Trigger analysis
    resp_trigger = client.post(f"/projects/{proj_id}/analyze")
    assert resp_trigger.status_code == 202
    data_trigger = resp_trigger.json()
    assert data_trigger["project_id"] == proj_id
    assert data_trigger["status"] in ("running", "completed")

    # 2. Poll status
    resp_status = client.get(f"/projects/{proj_id}/status")
    assert resp_status.status_code == 200
    data_status = resp_status.json()
    assert data_status["project_id"] == proj_id
    assert "progress_percent" in data_status
    assert "step" in data_status


def test_api_docs_endpoints(test_project):
    """Test GET /projects/{id}/docs and GET /projects/{id}/docs/download endpoints."""
    proj_id, _ = test_project
    client = TestClient(app)

    # Run analysis first so docs exist
    execute_analysis_sync(proj_id)

    # 1. Fetch docs JSON
    resp_docs = client.get(f"/projects/{proj_id}/docs")
    assert resp_docs.status_code == 200
    docs_json = resp_docs.json()
    assert docs_json["project_id"] == proj_id
    assert "# Architecture & Repository Documentation" in docs_json["overview_md"]

    # 2. Download markdown attachment
    resp_download = client.get(f"/projects/{proj_id}/docs/download")
    assert resp_download.status_code == 200
    assert "text/markdown" in resp_download.headers.get("content-type", "")
    assert "ARCHITECTURE.md" in resp_download.headers.get("content-disposition", "")
