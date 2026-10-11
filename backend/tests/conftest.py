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
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db.session import Base, get_db
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
        DATABASE_URL=f"sqlite:///{temp_workspace}/test.db",
        DEBUG=True,
    )


@pytest.fixture
def test_db(temp_workspace: Path) -> Generator[Session, None, None]:
    """Provide an isolated database session for unit tests."""
    db_file = temp_workspace / "unit_test.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(test_settings: Settings, temp_workspace: Path) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with isolated workspace and database overrides."""
    db_file = temp_workspace / "client_test.db"
    test_engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def create_in_memory_zip(file_dict: dict[str, str | bytes]) -> io.BytesIO:
    """
    Create an in-memory ZIP buffer with specified relative filenames and contents.
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
