"""
Pytest configuration and shared fixtures for unit and integration testing.
"""

import io
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Generator
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app


@pytest.fixture
def temp_workspace() -> Generator[Path, None, None]:
    """Provide a clean temporary directory for test workspace isolation."""
    temp_dir = Path(tempfile.mkdtemp(prefix="test_workspace_"))
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_settings(temp_workspace: Path) -> Settings:
    """Settings override with temporary workspace."""
    return Settings(
        WORKSPACE_DIR=temp_workspace,
        MAX_UPLOAD_SIZE_MB=5,
        MAX_FILE_COUNT=50,
        DEBUG=True,
    )


@pytest.fixture
def client(test_settings: Settings) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with overridden configuration."""
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_in_memory_zip(file_dict: dict[str, str | bytes]) -> io.BytesIO:
    """
    Create an in-memory ZIP buffer with specified relative filenames and contents.
    
    Args:
        file_dict: Mapping of relative filepath -> string or byte content.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filepath, content in file_dict.items():
            if isinstance(content, str):
                zf.writestr(filepath, content.encode("utf-8"))
            else:
                zf.writestr(filepath, content)
    buffer.seek(0)
    return buffer


def create_malicious_zip_slip_relative() -> io.BytesIO:
    """
    Create a malicious ZIP containing a path traversal entry (e.g., ../../evil.py).
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("app/main.py", "print('normal file')")
        # Path traversal payload attempting to escape target directory
        zf.writestr("../../evil_escape.py", "# Malicious payload outside destination")
    buffer.seek(0)
    return buffer


def create_malicious_zip_slip_absolute() -> io.BytesIO:
    """
    Create a malicious ZIP containing an absolute path entry (e.g., /tmp/evil.py).
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("/tmp/evil_absolute.py", "# Malicious absolute path payload")
    buffer.seek(0)
    return buffer
