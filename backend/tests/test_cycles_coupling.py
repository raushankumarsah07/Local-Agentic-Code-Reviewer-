"""
Tests for Phase 7c: Circular Dependencies (Tarjan's SCC) & Coupling Analysis.
Verifies cycle detection, self-loops, god-module degree/betweenness centrality,
and architecture analysis REST API endpoints.
"""

import io
import zipfile
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
import networkx as nx

from app.analysis.architecture import ArchitectureAnalyzer
from app.db.models import Finding
from app.main import app


# --- Test Code Fixtures ---

MODULE_A_CODE = """
import module_b

def func_a():
    return module_b.func_b() + 1
"""

MODULE_B_CODE = """
import module_a

def func_b():
    return module_a.func_a() * 2
"""

MODULE_C_CODE = """
# Independent leaf
def leaf_action():
    return "ok"
"""

GOD_MODULE_CODE = """
import sub_1
import sub_2
import sub_3
import sub_4
import sub_5

def central_orchestrator():
    return sub_1.run() + sub_2.run() + sub_3.run() + sub_4.run() + sub_5.run()
"""

SUB_TEMPLATE = """
import god

def run():
    return god.central_orchestrator()
"""


def test_tarjan_detects_mutual_2_node_cycle():
    """Verify Tarjan's SCC detects immediate mutual circular dependencies (A <-> B)."""
    g = nx.DiGraph()
    g.add_node("module_a.py", is_external=False, line_count=6)
    g.add_node("module_b.py", is_external=False, line_count=6)
    g.add_edge("module_a.py", "module_b.py", imported_symbols=["func_b"])
    g.add_edge("module_b.py", "module_a.py", imported_symbols=["func_a"])

    analyzer = ArchitectureAnalyzer()
    findings = analyzer.detect_circular_dependencies(g, "proj_test")

    assert len(findings) == 1
    f = findings[0]
    assert f["type"] == "cycle"
    assert f["severity"] == "Critical"
    assert f["source_tool"] == "tarjan_scc"
    assert "module_a.py" in f["title"] and "module_b.py" in f["title"]
    assert "Circular Import Chain" in f["evidence_snippet"]


def test_tarjan_detects_3_node_cycle():
    """Verify Tarjan's SCC detects 3-node cycles (A -> B -> C -> A)."""
    g = nx.DiGraph()
    g.add_node("a.py", is_external=False, line_count=5)
    g.add_node("b.py", is_external=False, line_count=5)
    g.add_node("c.py", is_external=False, line_count=5)
    g.add_edge("a.py", "b.py")
    g.add_edge("b.py", "c.py")
    g.add_edge("c.py", "a.py")

    analyzer = ArchitectureAnalyzer()
    findings = analyzer.detect_circular_dependencies(g, "proj_test")

    assert len(findings) == 1
    f = findings[0]
    assert f["type"] == "cycle"
    assert f["severity"] == "High"
    assert "3 files" in f["title"]


def test_dag_returns_zero_cycle_findings():
    """A clean directed acyclic graph (no cycles) should yield zero cycle findings."""
    g = nx.DiGraph()
    g.add_node("main.py", is_external=False, line_count=10)
    g.add_node("service.py", is_external=False, line_count=20)
    g.add_node("dao.py", is_external=False, line_count=15)
    g.add_edge("main.py", "service.py")
    g.add_edge("service.py", "dao.py")

    analyzer = ArchitectureAnalyzer()
    findings = analyzer.detect_circular_dependencies(g, "proj_test")
    assert len(findings) == 0


def test_god_module_coupling_detection():
    """Verify coupling analyzer detects hub/god module with high degree & betweenness centrality."""
    g = nx.DiGraph()
    g.add_node("god.py", is_external=False, line_count=100)

    # 6 satellite modules import god.py and god.py imports them back
    for i in range(1, 7):
        sub_name = f"sub_{i}.py"
        g.add_node(sub_name, is_external=False, line_count=20)
        g.add_edge("god.py", sub_name)
        g.add_edge(sub_name, "god.py")

    analyzer = ArchitectureAnalyzer(total_degree_threshold=5, betweenness_threshold=0.10)
    findings = analyzer.detect_god_modules(g, "proj_test")

    assert len(findings) >= 1
    god_finding = next(f for f in findings if f["file"] == "god.py")
    assert god_finding["type"] == "coupling"
    assert "God Module" in god_finding["title"]
    assert god_finding["source_tool"] == "coupling_analyzer"
    assert "Betweenness Centrality" in god_finding["evidence_snippet"]


# --- API Endpoint Integration Test ---

def test_architecture_api_workflow(client: TestClient):
    """End-to-end integration test of project upload and architecture analysis endpoint."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("module_a.py", MODULE_A_CODE)
        zf.writestr("module_b.py", MODULE_B_CODE)
        zf.writestr("module_c.py", MODULE_C_CODE)
    zip_buffer.seek(0)

    # 1. Upload repo
    upload_res = client.post(
        "/projects/upload",
        files={"file": ("test_arch_repo.zip", zip_buffer, "application/zip")},
    )
    assert upload_res.status_code == 201
    project_id = upload_res.json()["project_id"]

    # 2. Run architecture analysis
    arch_res = client.post(f"/projects/{project_id}/analyze/architecture")
    assert arch_res.status_code == 200
    data = arch_res.json()

    assert data["cycles_count"] >= 1
    assert data["total_findings"] >= 1

    # 3. Query findings endpoint specifically for cycle type
    findings_res = client.get(f"/projects/{project_id}/findings?type=cycle")
    assert findings_res.status_code == 200
    cycle_findings = findings_res.json()["findings"]

    assert len(cycle_findings) >= 1
    assert any("Circular Dependency Cycle" in f["title"] for f in cycle_findings)
    assert any(f["severity"] in ("Critical", "High") for f in cycle_findings)

    # 4. Summary check
    summary_res = client.get(f"/projects/{project_id}/findings/summary")
    assert summary_res.status_code == 200
    assert "cycle" in summary_res.json()["by_type"]
