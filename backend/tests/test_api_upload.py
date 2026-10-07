"""
Integration tests for FastAPI endpoints: /health, /projects/upload, and /projects.
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
    """Test POST /projects/upload with a valid ZIP file creates the project and extracts files."""
    files = {
        "calculator/math.py": "def add(x, y):\n    return x + y\n",
        "calculator/__init__.py": "",
        "README.md": "# Calculator Project",
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


def test_list_projects_after_upload(client: TestClient):
    """Test GET /projects lists all currently extracted workspace project directories."""
    files = {"app.py": "print('ok')"}
    zip_buffer = create_in_memory_zip(files)

    # Upload project
    upload_res = client.post(
        "/projects/upload",
        files={"file": ("project_alpha.zip", zip_buffer, "application/zip")},
    )
    assert upload_res.status_code == 201
    created_id = upload_res.json()["project_id"]

    # List projects
    list_res = client.get("/projects")
    assert list_res.status_code == 200
    project_list = list_res.json()
    assert any(p["project_id"] == created_id for p in project_list)
