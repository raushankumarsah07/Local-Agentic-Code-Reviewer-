"""
Tests for Phase 7b: Dead-Code Candidate Static Analyzer.
Verifies entry point detection, graph reachability (BFS/DFS), Vulture integration,
false-positive documentation (decorators, __all__, dynamic access), and REST endpoints.
"""

import io
import zipfile
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
import networkx as nx

from app.analysis.dead_code import (
    DeadCodeAnalyzer,
    file_has_main_block,
    extract_file_exported_names,
    extract_function_decorators,
)
from app.db.models import Finding
from app.main import app


# --- Test Code Fixtures ---

MAIN_CODE = """
import used_helper

def main():
    print(used_helper.do_work())

if __name__ == "__main__":
    main()
"""

USED_HELPER_CODE = """
def do_work():
    return "work done"
"""

ORPHAN_MODULE_CODE = """
def abandoned_calculation(a, b):
    # This entire file is never imported by main.py
    return a * b + 100

def unused_internal_subtask():
    return 42
"""

DECORATED_CODE = """
class MockApp:
    def get(self, path):
        def decorator(f): return f
        return decorator

app = MockApp()

@app.get("/items")
def list_items():
    return ["item1", "item2"]

@property
def computed_field():
    return 123
"""

ALL_EXPORTS_CODE = """
__all__ = ["public_library_api"]

def public_library_api():
    return "available for external consumers"

def private_unexported_func():
    return "private"
"""


def test_file_has_main_block(tmp_path: Path):
    """Verify AST accurately detects if __name__ == '__main__': blocks."""
    main_file = tmp_path / "script.py"
    main_file.write_text(MAIN_CODE)
    assert file_has_main_block(main_file) is True

    non_main_file = tmp_path / "lib.py"
    non_main_file.write_text(USED_HELPER_CODE)
    assert file_has_main_block(non_main_file) is False


def test_extract_file_exported_names(tmp_path: Path):
    """Verify extraction of symbols listed in __all__."""
    all_file = tmp_path / "api.py"
    all_file.write_text(ALL_EXPORTS_CODE)
    exported = extract_file_exported_names(all_file)
    assert "public_library_api" in exported
    assert "private_unexported_func" not in exported


def test_extract_function_decorators(tmp_path: Path):
    """Verify AST decorator extraction for functions."""
    dec_file = tmp_path / "routes.py"
    dec_file.write_text(DECORATED_CODE)
    decorators = extract_function_decorators(dec_file)
    assert "list_items" in decorators
    assert any("get" in d for d in decorators["list_items"])
    assert "computed_field" in decorators
    assert "property" in decorators["computed_field"]


def test_graph_reachability_bfs_dfs():
    """Verify that BFS/DFS traversal correctly identifies unreachable files."""
    g = nx.DiGraph()
    # main.py -> used_helper.py
    g.add_node("main.py", is_external=False, line_count=10)
    g.add_node("used_helper.py", is_external=False, line_count=5)
    g.add_node("orphan.py", is_external=False, line_count=15)
    g.add_edge("main.py", "used_helper.py")

    analyzer = DeadCodeAnalyzer(entry_points=["main.py"])
    reachable = analyzer.compute_reachable_files(g, ["main.py"])

    assert "main.py" in reachable
    assert "used_helper.py" in reachable
    assert "orphan.py" not in reachable


def test_unreachable_file_flagged_as_candidate(tmp_path: Path):
    """An unreachable file should generate a dead-code candidate finding."""
    (tmp_path / "main.py").write_text(MAIN_CODE)
    (tmp_path / "used_helper.py").write_text(USED_HELPER_CODE)
    (tmp_path / "orphan.py").write_text(ORPHAN_MODULE_CODE)

    analyzer = DeadCodeAnalyzer()
    findings = analyzer.analyze_project(tmp_path, "proj_test")

    unreachable_findings = [f for f in findings if "Unreachable file" in f["title"]]
    assert len(unreachable_findings) == 1
    f = unreachable_findings[0]
    assert f["file"] == "orphan.py"
    assert f["type"] == "dead_code"
    assert "candidate" in f["title"].lower()
    assert "candidate" in f["explanation"].lower()


def test_false_positive_documentation_on_decorators(tmp_path: Path):
    """Symbols with framework decorators should include false-positive documentation."""
    (tmp_path / "main.py").write_text(MAIN_CODE)
    (tmp_path / "used_helper.py").write_text(USED_HELPER_CODE)
    (tmp_path / "routes.py").write_text(DECORATED_CODE)

    analyzer = DeadCodeAnalyzer(entry_points=["main.py"])
    findings = analyzer.analyze_project(tmp_path, "proj_test")

    # Check for findings in routes.py
    for f in findings:
        if "list_items" in f["title"]:
            assert "decorator" in f["explanation"].lower()
            assert "candidate" in f["title"].lower()


def test_false_positive_documentation_on_all_exports(tmp_path: Path):
    """Symbols in __all__ should document public library exports."""
    (tmp_path / "main.py").write_text(MAIN_CODE)
    (tmp_path / "used_helper.py").write_text(USED_HELPER_CODE)
    (tmp_path / "api.py").write_text(ALL_EXPORTS_CODE)

    analyzer = DeadCodeAnalyzer(entry_points=["main.py"])
    findings = analyzer.analyze_project(tmp_path, "proj_test")

    for f in findings:
        if "public_library_api" in f["title"]:
            assert "__all__" in f["explanation"] or "export" in f["explanation"].lower()


# --- API Endpoint Integration Test ---

def test_dead_code_api_workflow(client: TestClient):
    """End-to-end test of project upload and dead-code analysis API trigger."""
    # 1. Package test repo with entry point and an unreachable orphan
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("main.py", MAIN_CODE)
        zf.writestr("used_helper.py", USED_HELPER_CODE)
        zf.writestr("orphan.py", ORPHAN_MODULE_CODE)
    zip_buffer.seek(0)

    # 2. Upload
    upload_res = client.post(
        "/projects/upload",
        files={"file": ("test_dead_code_repo.zip", zip_buffer, "application/zip")},
    )
    assert upload_res.status_code == 201
    project_id = upload_res.json()["project_id"]

    # 3. Trigger dead-code analysis
    dead_code_res = client.post(f"/projects/{project_id}/analyze/dead-code")
    assert dead_code_res.status_code == 200
    res_data = dead_code_res.json()

    assert res_data["unreachable_files_count"] >= 1
    assert res_data["findings_count"] >= 1
    assert "main.py" in res_data["entry_points"]

    # 4. Query findings endpoint for dead_code type
    findings_res = client.get(f"/projects/{project_id}/findings?type=dead_code")
    assert findings_res.status_code == 200
    findings = findings_res.json()["findings"]
    assert len(findings) >= 1
    assert all(f["type"] == "dead_code" for f in findings)
    assert any("Candidate" in f["title"] for f in findings)
