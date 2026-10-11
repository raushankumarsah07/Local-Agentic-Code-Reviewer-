"""
Integration tests for FastAPI endpoints:
- GET /health
- POST /projects/upload
- GET /projects
- GET /projects/{project_id}
- GET /projects/{project_id}/files
- DELETE /projects/{project_id}
"""

import io
from fastapi.testclient import TestClient
from tests.conftest import (
    create_in_memory_zip,
    create_malicious_zip_slip_relative,
)


def test_health_endpoint(client: TestClient):
    """Test GET /health returns 200 and expected diagnostic structure."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "ollama_service" in data
    assert "configured_llm_model" in data["ollama_service"]


def test_root_endpoint(client: TestClient):
    """Test GET / returns quick links to documentation and upload endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["documentation"] == "/docs"
    assert data["health_check"] == "/health"


def test_upload_valid_project_zip(client: TestClient):
    """Test POST /projects/upload with a valid ZIP file creates the project, scans, and stores files."""
    files = {
        "calculator/math.py": "def add(x, y):\n    return x + y\n",
        "calculator/__init__.py": "# init file\n",
        "README.md": "# Calculator Project\nDocumentation here.\n",
    }
    zip_buffer = create_in_memory_zip(files)

    response = client.post(
        "/projects/upload",
        files={"file": ("sample_calculator.zip", zip_buffer, "application/zip")},
    )

    assert response.status_code == 201
    data = response.json()
    assert "project_id" in data
    assert data["project_name"] == "sample_calculator"
    assert data["file_count"] == 3
    assert data["total_lines"] == 5  # 2 + 1 + 2
    assert "Python" in data["languages"]
    assert data["languages"]["Python"] == 2
    assert data["languages"]["Markdown"] == 1
    assert data["skipped_count"] == 0
    assert "target_directory" in data


def test_upload_malicious_zip_slip_rejected(client: TestClient):
    """
    Test POST /projects/upload with a malicious zip-slip archive is strictly rejected
    with HTTP 400 and security violation message.
    """
    malicious_zip = create_malicious_zip_slip_relative()

    response = client.post(
        "/projects/upload",
        files={"file": ("exploit_attempt.zip", malicious_zip, "application/zip")},
    )

    assert response.status_code == 400
    data = response.json()
    assert "Security Violation (Zip-Slip)" in data["detail"]


def test_upload_non_zip_file_rejected(client: TestClient):
    """Test POST /projects/upload rejects files that do not have a .zip extension."""
    fake_file = io.BytesIO(b"print('Hello world')")

    response = client.post(
        "/projects/upload",
        files={"file": ("script.py", fake_file, "text/x-python")},
    )

    assert response.status_code == 400
    data = response.json()
    assert "Only .zip archives are supported" in data["detail"]


def test_upload_corrupt_zip_rejected(client: TestClient):
    """Test POST /projects/upload rejects malformed or corrupt zip files."""
    corrupt_file = io.BytesIO(b"Not a valid zip content")

    response = client.post(
        "/projects/upload",
        files={"file": ("broken.zip", corrupt_file, "application/zip")},
    )

    assert response.status_code == 400
    data = response.json()
    assert "Failed to extract ZIP" in data["detail"]


def test_list_and_get_project_files(client: TestClient):
    """Test GET /projects, GET /projects/{id}, and GET /projects/{id}/files."""
    files = {
        "src/app.py": "print('hello')\n",
        "src/util.py": "x = 10\ny = 20\n",
        "README.md": "# Docs\n",
    }
    zip_buffer = create_in_memory_zip(files)

    # 1. Upload project
    upload_res = client.post(
        "/projects/upload",
        files={"file": ("project_test.zip", zip_buffer, "application/zip")},
    )
    assert upload_res.status_code == 201
    project_id = upload_res.json()["project_id"]

    # 2. List projects
    list_res = client.get("/projects")
    assert list_res.status_code == 200
    project_list = list_res.json()
    assert any(p["project_id"] == project_id for p in project_list)

    # 3. Get single project detail
    detail_res = client.get(f"/projects/{project_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["project_id"] == project_id
    assert detail_data["total_files"] == 3
    assert detail_data["total_lines"] == 4  # 1 + 2 + 1
    assert detail_data["languages"]["Python"] == 2

    # 4. List all files for the project
    files_res = client.get(f"/projects/{project_id}/files")
    assert files_res.status_code == 200
    files_data = files_res.json()
    assert files_data["total_files"] == 3
    assert files_data["count"] == 3
    file_paths = [f["path"] for f in files_data["files"]]
    assert "src/app.py" in file_paths
    assert "README.md" in file_paths

    # 5. Filter files by language
    py_files_res = client.get(f"/projects/{project_id}/files?language=Python")
    assert py_files_res.status_code == 200
    py_files_data = py_files_res.json()
    assert py_files_data["count"] == 2
    for f in py_files_data["files"]:
        assert f["language"] == "Python"

    # 6. Delete project
    del_res = client.delete(f"/projects/{project_id}")
    assert del_res.status_code == 200

    # 7. Verify 404 after deletion
    files_after_del = client.get(f"/projects/{project_id}/files")
    assert files_after_del.status_code == 404


def test_get_nonexistent_project_returns_404(client: TestClient):
    """Test GET /projects/nonexistent/files returns 404."""
    response = client.get("/projects/does_not_exist/files")
    assert response.status_code == 404


def test_project_parse_and_ast_endpoints(client: TestClient):
    """Test AST parsing endpoints: POST /parse, GET /ast, GET /entities."""
    files = {
        "calculator.py": (
            "class BasicCalc:\n"
            "    def add(self, a, b):\n"
            "        return a + b\n"
            "\n"
            "class SciCalc(BasicCalc):\n"
            "    def square(self, x):\n"
            "        return x * x\n"
        ),
        "broken.py": "def bad(\n    return 42\n",  # deliberate syntax error
    }
    zip_buffer = create_in_memory_zip(files)

    # 1. Upload project
    upload_res = client.post(
        "/projects/upload",
        files={"file": ("calc_proj.zip", zip_buffer, "application/zip")},
    )
    assert upload_res.status_code == 201
    project_id = upload_res.json()["project_id"]

    # 2. Trigger AST parse
    parse_res = client.post(f"/projects/{project_id}/parse")
    assert parse_res.status_code == 200
    parse_data = parse_res.json()

    assert parse_data["parsed_files_count"] == 1
    assert parse_data["unparsable_files_count"] == 1  # broken.py caught
    assert len(parse_data["unparsable_files"]) == 1
    assert parse_data["unparsable_files"][0]["file"] == "broken.py"
    assert parse_data["total_classes"] == 2
    assert parse_data["total_methods"] == 2

    # 3. Query AST for specific file
    ast_res = client.get(f"/projects/{project_id}/ast?file_path=calculator.py")
    assert ast_res.status_code == 200
    ast_data = ast_res.json()
    assert ast_data["is_parsable"] is True
    assert len(ast_data["classes"]) == 2
    assert ast_data["classes"][0]["name"] == "BasicCalc"
    assert ast_data["classes"][1]["name"] == "SciCalc"
    assert ast_data["classes"][1]["bases"] == ["BasicCalc"]

    # 4. Query AST for broken file
    broken_ast_res = client.get(f"/projects/{project_id}/ast?file_path=broken.py")
    assert broken_ast_res.status_code == 200
    broken_ast_data = broken_ast_res.json()
    assert broken_ast_data["is_parsable"] is False
    assert "SyntaxError" in broken_ast_data["error_message"]

    # 5. Query stored entities
    entities_res = client.get(f"/projects/{project_id}/entities?entity_type=class")
    assert entities_res.status_code == 200
    entities = entities_res.json()
    assert len(entities) == 2
    class_names = [e["name"] for e in entities]
    assert "BasicCalc" in class_names
    assert "SciCalc" in class_names


def test_get_source_file_success(client: TestClient):
    """Test GET /projects/{id}/files/{path} returns source with 1-indexed line numbers."""
    code_content = "def add(x, y):\n    return x + y\n"
    zip_buffer = create_in_memory_zip({"math/calc.py": code_content})

    upload_res = client.post(
        "/projects/upload",
        files={"file": ("src_test.zip", zip_buffer, "application/zip")},
    )
    assert upload_res.status_code == 201
    project_id = upload_res.json()["project_id"]

    res = client.get(f"/projects/{project_id}/files/math/calc.py")
    assert res.status_code == 200
    data = res.json()

    assert data["project_id"] == project_id
    assert data["file_path"] == "math/calc.py"
    assert data["language"] == "Python"
    assert data["total_lines"] == 2
    assert len(data["lines"]) == 2
    assert data["lines"][0]["line_number"] == 1
    assert data["lines"][0]["content"] == "def add(x, y):"
    assert data["lines"][1]["line_number"] == 2
    assert data["lines"][1]["content"] == "    return x + y"


def test_get_source_file_path_traversal_refused(client: TestClient):
    """
    CRITICAL SECURITY CHECK:
    Verify that requesting ../../etc/passwd or similar paths through the file endpoint
    is strictly refused with HTTP 400 Bad Request and Security Violation details.
    """
    zip_buffer = create_in_memory_zip({"app.py": "print('normal')\n"})
    upload_res = client.post(
        "/projects/upload",
        files={"file": ("sec_test.zip", zip_buffer, "application/zip")},
    )
    assert upload_res.status_code == 201
    project_id = upload_res.json()["project_id"]

    # 1. Test query param path traversal (../../etc/passwd)
    res_query = client.get(f"/projects/{project_id}/source?path=../../etc/passwd")
    assert res_query.status_code == 400
    assert "Path traversal attempt detected" in res_query.json()["detail"]

    # 2. Test URL-encoded path traversal (..%2F..%2Fetc%2Fpasswd)
    res_enc = client.get(f"/projects/{project_id}/files/..%2F..%2Fetc%2Fpasswd")
    assert res_enc.status_code == 400
    assert "Path traversal attempt detected" in res_enc.json()["detail"]

    # 3. Test deeper encoded path traversal (..%2F..%2F..%2F..%2Fetc%2Fpasswd)
    res_deep = client.get(f"/projects/{project_id}/files/..%2F..%2F..%2F..%2Fetc%2Fpasswd")
    assert res_deep.status_code == 400
    assert "Path traversal attempt detected" in res_deep.json()["detail"]


def test_get_source_file_not_found(client: TestClient):
    """Verify requesting a non-existent file inside valid project returns 404."""
    zip_buffer = create_in_memory_zip({"app.py": "print('ok')"})
    upload_res = client.post(
        "/projects/upload",
        files={"file": ("missing_test.zip", zip_buffer, "application/zip")},
    )
    assert upload_res.status_code == 201
    project_id = upload_res.json()["project_id"]

    res = client.get(f"/projects/{project_id}/files/does_not_exist.py")
    assert res.status_code == 404

