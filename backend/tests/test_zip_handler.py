"""
Unit tests for safe ZIP extraction and security validation.
"""

from pathlib import Path
import pytest

from app.ingestion.zip_handler import (
    ZipBombError,
    ZipExtractionError,
    ZipSlipError,
    safe_extract_zip,
)
from tests.conftest import (
    create_in_memory_zip,
    create_malicious_zip_slip_absolute,
    create_malicious_zip_slip_relative,
)


def test_safe_extract_valid_zip(temp_workspace: Path):
    """Verify that safe files in a normal zip archive are extracted cleanly."""
    files = {
        "project/main.py": "def main():\n    print('Hello World')\n",
        "project/utils/helper.py": "def add(a, b):\n    return a + b\n",
        "README.md": "# Sample Project\nThis is a sample.",
    }
    zip_buffer = create_in_memory_zip(files)
    dest_dir = temp_workspace / "valid_project"

    result = safe_extract_zip(
        zip_source=zip_buffer,
        destination_dir=dest_dir,
        project_id="valid_123",
        max_size_bytes=10 * 1024 * 1024,
        max_file_count=100,
    )

    assert result.project_id == "valid_123"
    assert result.extracted_files_count == 3
    assert result.skipped_files_count == 0
    assert (dest_dir / "project" / "main.py").exists()
    assert (dest_dir / "project" / "utils" / "helper.py").exists()
    assert (dest_dir / "README.md").exists()
    assert (dest_dir / "project" / "main.py").read_text(encoding="utf-8") == files["project/main.py"]


def test_zip_slip_relative_path_rejected(temp_workspace: Path):
    """Verify that a ZIP attempting path traversal via relative paths (../) is rejected."""
    zip_buffer = create_malicious_zip_slip_relative()
    dest_dir = temp_workspace / "evil_project"

    with pytest.raises(ZipSlipError) as exc_info:
        safe_extract_zip(
            zip_source=zip_buffer,
            destination_dir=dest_dir,
            project_id="evil_123",
        )

    assert "Zip-Slip vulnerability detected" in str(exc_info.value)
    # Ensure no files were leaked outside or left behind in destination
    assert not (temp_workspace / "evil_escape.py").exists()


def test_zip_slip_absolute_path_rejected(temp_workspace: Path):
    """Verify that a ZIP with absolute paths is strictly rejected."""
    zip_buffer = create_malicious_zip_slip_absolute()
    dest_dir = temp_workspace / "evil_abs_project"

    with pytest.raises(ZipSlipError) as exc_info:
        safe_extract_zip(
            zip_source=zip_buffer,
            destination_dir=dest_dir,
            project_id="evil_abs_123",
        )

    assert "Malicious absolute path detected" in str(exc_info.value)


def test_zip_bomb_file_count_limit(temp_workspace: Path):
    """Verify that exceeding the max allowed file count raises ZipBombError."""
    # Create an archive with 15 files, but set limit to 10
    files = {f"file_{i}.py": f"# Content {i}" for i in range(15)}
    zip_buffer = create_in_memory_zip(files)
    dest_dir = temp_workspace / "bomb_count_project"

    with pytest.raises(ZipBombError) as exc_info:
        safe_extract_zip(
            zip_source=zip_buffer,
            destination_dir=dest_dir,
            project_id="bomb_count",
            max_file_count=10,
        )

    assert "Archive exceeds maximum allowed entries limit" in str(exc_info.value)


def test_zip_bomb_size_limit(temp_workspace: Path):
    """Verify that exceeding the max uncompressed byte limit raises ZipBombError."""
    # Create 1 MB of repetitive data and set limit to 500 KB
    large_content = "A" * (1024 * 1024)
    zip_buffer = create_in_memory_zip({"large_file.py": large_content})
    dest_dir = temp_workspace / "bomb_size_project"

    with pytest.raises(ZipBombError) as exc_info:
        safe_extract_zip(
            zip_source=zip_buffer,
            destination_dir=dest_dir,
            project_id="bomb_size",
            max_size_bytes=500 * 1024,
        )

    assert "Uncompressed archive size exceeds limit" in str(exc_info.value)


def test_ignore_rules_filtering(temp_workspace: Path):
    """Verify that .git, node_modules, venv, and binary files are skipped automatically."""
    files = {
        "src/app.py": "print('valid')",
        ".git/config": "[core] repositoryformatversion = 0",
        "node_modules/package/index.js": "console.log('ignored')",
        "venv/bin/activate": "# ignored venv",
        "__pycache__/app.cpython-311.pyc": b"\x00\x01\x02",
        "assets/logo.png": b"\x89PNG\r\n\x1a\n",
        "docs/manual.pdf": b"%PDF-1.4",
    }
    zip_buffer = create_in_memory_zip(files)
    dest_dir = temp_workspace / "filter_project"

    result = safe_extract_zip(
        zip_source=zip_buffer,
        destination_dir=dest_dir,
        project_id="filter_test",
    )

    # Only src/app.py should be extracted (1 valid code file, 6 ignored)
    assert result.extracted_files_count == 1
    assert result.skipped_files_count == 6
    assert (dest_dir / "src" / "app.py").exists()
    assert not (dest_dir / ".git").exists()
    assert not (dest_dir / "node_modules").exists()
    assert not (dest_dir / "venv").exists()
    assert not (dest_dir / "__pycache__").exists()
    assert not (dest_dir / "assets" / "logo.png").exists()


def test_corrupt_zip_handling(temp_workspace: Path):
    """Verify that corrupt or invalid ZIP data raises ZipExtractionError."""
    import io
    corrupt_buffer = io.BytesIO(b"This is definitely not a zip file header")
    dest_dir = temp_workspace / "corrupt_project"

    with pytest.raises(ZipExtractionError) as exc_info:
        safe_extract_zip(
            zip_source=corrupt_buffer,
            destination_dir=dest_dir,
            project_id="corrupt_test",
        )

    assert "Corrupt or invalid ZIP archive" in str(exc_info.value)
