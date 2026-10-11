"""
Unit and integration tests for the dependency graph builder and metrics (app/graph/).
Tests import resolution, package/__init__.py handling, relative imports,
external library classification, in-degree/out-degree calculation, and JSON export.
"""

from pathlib import Path
from fastapi.testclient import TestClient

from app.graph.builder import DependencyGraphBuilder
from app.graph.metrics import compute_graph_metrics
from tests.conftest import create_in_memory_zip


def test_dependency_graph_builder_on_fixture(temp_workspace: Path):
    """
    Test dependency graph generation on a multi-module repository with:
    - Internal absolute imports
    - Package and __init__.py imports
    - Relative imports
    - External stdlib / third-party libraries
    """
    repo_dir = temp_workspace / "multi_module_repo"
    repo_dir.mkdir()

    # 1. Main entrypoint
    (repo_dir / "main.py").write_text(
        "import os\n"
        "from calculator import BasicCalculator\n"
        "from utils.helpers import validate_number\n",
        encoding="utf-8",
    )

    # 2. Calculator module
    (repo_dir / "calculator.py").write_text(
        "import math\n"
        "from utils.helpers import validate_number, format_result\n",
        encoding="utf-8",
    )

    # 3. Utils package with __init__.py and relative import
    utils_dir = repo_dir / "utils"
    utils_dir.mkdir()
    (utils_dir / "__init__.py").write_text(
        "from .helpers import validate_number\n",
        encoding="utf-8",
    )
    (utils_dir / "helpers.py").write_text(
        "import sys\n"
        "def validate_number(x): return True\n"
        "def format_result(x): return x\n",
        encoding="utf-8",
    )

    # 4. Standalone tool file
    (repo_dir / "tool.py").write_text(
        "import json\n",
        encoding="utf-8",
    )

    # Build Graph
    builder = DependencyGraphBuilder(project_root=repo_dir, project_id="test_repo")
    graph_data = builder.export_json(include_external=True)

    # Assert internal nodes
    node_ids = {n.id for n in graph_data.nodes}
    assert "main.py" in node_ids
    assert "calculator.py" in node_ids
    assert "utils/__init__.py" in node_ids
    assert "utils/helpers.py" in node_ids
    assert "tool.py" in node_ids

    # Assert external nodes
    assert "os" in node_ids
    assert "math" in node_ids
    assert "sys" in node_ids
    assert "json" in node_ids

    # Find nodes by ID for degree assertions
    node_map = {n.id: n for n in graph_data.nodes}

    # utils/helpers.py is imported by main.py, calculator.py, and utils/__init__.py -> in_degree == 3
    assert node_map["utils/helpers.py"].in_degree == 3
    # main.py imports calculator.py, utils/helpers.py, and os -> out_degree == 3
    assert node_map["main.py"].out_degree == 3
    # main.py is never imported by other files -> in_degree == 0
    assert node_map["main.py"].in_degree == 0

    # Assert Edges
    edge_pairs = {(e.source, e.target) for e in graph_data.edges}

    # Verify Internal Edges
    assert ("main.py", "calculator.py") in edge_pairs
    assert ("main.py", "utils/helpers.py") in edge_pairs
    assert ("calculator.py", "utils/helpers.py") in edge_pairs
    assert ("utils/__init__.py", "utils/helpers.py") in edge_pairs

    # Verify External Edges
    assert ("main.py", "os") in edge_pairs
    assert ("calculator.py", "math") in edge_pairs
    assert ("utils/helpers.py", "sys") in edge_pairs
    assert ("tool.py", "json") in edge_pairs

    # Verify imported symbols merged on edge
    calc_to_helpers = next(e for e in graph_data.edges if e.source == "calculator.py" and e.target == "utils/helpers.py")
    assert "format_result" in calc_to_helpers.imported_symbols
    assert "validate_number" in calc_to_helpers.imported_symbols


def test_dependency_graph_without_external_libraries(temp_workspace: Path):
    """Verify include_external=False excludes third-party/stdlib nodes."""
    repo_dir = temp_workspace / "internal_only_repo"
    repo_dir.mkdir()

    (repo_dir / "a.py").write_text("import b\nimport requests\n", encoding="utf-8")
    (repo_dir / "b.py").write_text("import os\n", encoding="utf-8")

    builder = DependencyGraphBuilder(project_root=repo_dir)
    graph_data = builder.export_json(include_external=False)

    node_ids = {n.id for n in graph_data.nodes}
    assert node_ids == {"a.py", "b.py"}
    assert graph_data.external_nodes_count == 0
    assert len(graph_data.edges) == 1
    assert graph_data.edges[0].source == "a.py"
    assert graph_data.edges[0].target == "b.py"


def test_relative_import_resolution_parent_levels(temp_workspace: Path):
    """Verify relative imports with level 1 (from .) and level 2 (from ..)."""
    repo_dir = temp_workspace / "pkg_repo"
    (repo_dir / "pkg" / "sub").mkdir(parents=True)
    (repo_dir / "pkg" / "core.py").write_text("class CoreService: pass\n", encoding="utf-8")
    (repo_dir / "pkg" / "sub" / "helper.py").write_text("def assist(): pass\n", encoding="utf-8")

    worker_file = repo_dir / "pkg" / "sub" / "worker.py"
    worker_file.write_text(
        "from .helper import assist\n"
        "from ..core import CoreService\n",
        encoding="utf-8",
    )

    builder = DependencyGraphBuilder(project_root=repo_dir)
    graph_data = builder.export_json(include_external=False)

    edge_pairs = {(e.source, e.target) for e in graph_data.edges}
    assert ("pkg/sub/worker.py", "pkg/sub/helper.py") in edge_pairs
    assert ("pkg/sub/worker.py", "pkg/core.py") in edge_pairs


def test_graph_api_endpoint(client: TestClient):
    """Test GET /projects/{project_id}/graph REST API endpoint."""
    files = {
        "main.py": "from service import run\n",
        "service.py": "import os\ndef run(): pass\n",
    }
    zip_buffer = create_in_memory_zip(files)

    # 1. Upload project
    upload_res = client.post(
        "/projects/upload",
        files={"file": ("graph_proj.zip", zip_buffer, "application/zip")},
    )
    assert upload_res.status_code == 201
    project_id = upload_res.json()["project_id"]

    # 2. Fetch Graph
    graph_res = client.get(f"/projects/{project_id}/graph?include_external=true")
    assert graph_res.status_code == 200
    data = graph_res.json()

    assert data["project_id"] == project_id
    assert data["total_nodes"] == 3  # main.py, service.py, os
    assert data["total_edges"] == 2  # main.py->service.py, service.py->os
    assert "metrics" in data
    assert data["metrics"]["is_dag"] is True
