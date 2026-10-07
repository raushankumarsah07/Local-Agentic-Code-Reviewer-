"""
Safe ZIP extraction module with robust security validations.
Guards against:
- Zip Slip (Path Traversal vulnerabilities via relative or absolute paths)
- Zip Bombs (Exceeding max uncompressed size limit or max file count)
- Unwanted files (.git, node_modules, venv, binaries, build artifacts)
"""

import os
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Set, Union


class ZipExtractionError(Exception):
    """Base exception for zip extraction failures."""
    pass


class ZipSlipError(ZipExtractionError):
    """Raised when a zip entry attempts path traversal outside destination folder."""
    pass


class ZipBombError(ZipExtractionError):
    """Raised when zip contents exceed safety size or file count thresholds."""
    pass


# Directories that should never be analyzed or extracted into workspace
IGNORED_DIR_NAMES: Set[str] = {
    ".git",
    ".github",
    ".svn",
    ".hg",
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    "__pycache__",
    "dist",
    "build",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
}

# Non-code binary and artifact extensions to ignore
IGNORED_EXTENSIONS: Set[str] = {
    # Binaries and compiled libraries
    ".exe", ".dll", ".so", ".dylib", ".bin", ".pyc", ".pyo", ".pyd", ".class", ".o", ".a",
    # Archives
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".7z", ".rar", ".jar", ".war",
    # Media & Assets
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".flac",
    # Fonts
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    # Documents & Databases
    ".pdf", ".docx", ".xlsx", ".sqlite", ".sqlite3", ".db",
}


@dataclass
class ExtractionResult:
    """Summary of extraction results."""
    project_id: str
    target_dir: Path
    extracted_files_count: int
    skipped_files_count: int
    total_uncompressed_bytes: int


def is_ignored_path(relative_path: str) -> bool:
    """
    Check if a file or directory path matches any ignored directory or binary extension.
    
    Args:
        relative_path: The file path string within the zip archive.
        
    Returns:
        True if the file should be skipped, False otherwise.
    """
    norm_path = relative_path.replace("\\", "/")
    parts = [p for p in norm_path.split("/") if p]

    # Check if any path segment matches an ignored folder name
    for part in parts:
        if part in IGNORED_DIR_NAMES or part.endswith(".egg-info"):
            return True

    # Check extension of the file
    ext = Path(norm_path).suffix.lower()
    if ext in IGNORED_EXTENSIONS:
        return True

    return False


def safe_extract_zip(
    zip_source: Union[str, Path, BinaryIO],
    destination_dir: Path,
    project_id: str,
    max_size_bytes: int = 50 * 1024 * 1024,
    max_file_count: int = 5000,
) -> ExtractionResult:
    """
    Safely extract a ZIP archive to destination_dir with full security validation.
    
    Steps:
    1. Verify valid ZIP structure.
    2. Check entry count against max_file_count.
    3. Validate every member path (strictly preventing Zip Slip / path traversal).
    4. Compute and check total uncompressed size (preventing Zip Bombs).
    5. Filter out ignored directories (.git, node_modules, etc.) and binary files.
    6. Extract allowed files safely and return summary metrics.
    
    Args:
        zip_source: Path to zip file or a readable file-like binary stream.
        destination_dir: Directory where files will be extracted.
        project_id: Unique identifier for the project.
        max_size_bytes: Maximum allowed total uncompressed size in bytes.
        max_file_count: Maximum allowed number of files.
        
    Returns:
        ExtractionResult containing file counts and target directory.
        
    Raises:
        ZipSlipError: If any archive member tries to write outside destination_dir.
        ZipBombError: If limits for file count or uncompressed size are exceeded.
        ZipExtractionError: If the zip archive is corrupt or invalid.
    """
    dest_path = Path(destination_dir).resolve()
    dest_path.mkdir(parents=True, exist_ok=True)

    extracted_count = 0
    skipped_count = 0
    total_bytes = 0

    try:
        with zipfile.ZipFile(zip_source, "r") as zf:
            infolist = zf.infolist()

            # 1. Total entry count check
            if len(infolist) > max_file_count:
                raise ZipBombError(
                    f"Archive exceeds maximum allowed entries limit ({len(infolist)} > {max_file_count})."
                )

            # 2. Pre-scan all members for Zip-Slip and cumulative size
            for member in infolist:
                # Disallow absolute paths in member name
                raw_filename = member.filename
                if os.path.isabs(raw_filename):
                    raise ZipSlipError(f"Malicious absolute path detected in ZIP entry: {raw_filename}")

                # Resolve target file path
                target_file_path = (dest_path / raw_filename).resolve()

                # Strictly ensure target_file_path is within dest_path (Prevents Zip Slip)
                try:
                    if not target_file_path.is_relative_to(dest_path):
                        raise ZipSlipError(
                            f"Zip-Slip vulnerability detected: '{raw_filename}' escapes target directory."
                        )
                except AttributeError:
                    # Fallback for Python versions without is_relative_to (safety guarantee)
                    if not str(target_file_path).startswith(str(dest_path) + os.sep) and target_file_path != dest_path:
                        raise ZipSlipError(
                            f"Zip-Slip vulnerability detected: '{raw_filename}' escapes target directory."
                        )

                # Disallow Unix symlink entries that could escape boundary
                is_symlink = (member.external_attr >> 16) & 0o170000 == 0o120000
                if is_symlink:
                    skipped_count += 1
                    continue

                # Ignore directory entries and ignored paths during size accumulation
                if member.is_dir() or is_ignored_path(raw_filename):
                    continue

                total_bytes += member.file_size
                if total_bytes > max_size_bytes:
                    raise ZipBombError(
                        f"Uncompressed archive size exceeds limit of {max_size_bytes / (1024 * 1024):.1f} MB."
                    )

            # 3. Extract safe files
            for member in infolist:
                raw_filename = member.filename

                # Skip directories (folders are created as needed for files)
                if member.is_dir():
                    continue

                # Skip symlinks and ignored paths (.git, node_modules, binary extensions)
                is_symlink = (member.external_attr >> 16) & 0o170000 == 0o120000
                if is_symlink or is_ignored_path(raw_filename):
                    skipped_count += 1
                    continue

                target_file_path = (dest_path / raw_filename).resolve()
                
                # Double-check relative path guarantee before writing
                if not target_file_path.is_relative_to(dest_path):
                    raise ZipSlipError(f"Zip-Slip path detected on write: {raw_filename}")

                # Ensure parent directories exist
                target_file_path.parent.mkdir(parents=True, exist_ok=True)

                # Write file content safely
                with zf.open(member, "r") as src, open(target_file_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)

                extracted_count += 1

    except (zipfile.BadZipFile, zipfile.LargeZipFile) as e:
        # Cleanup partially extracted files on failure
        if dest_path.exists():
            shutil.rmtree(dest_path, ignore_errors=True)
        raise ZipExtractionError(f"Corrupt or invalid ZIP archive: {str(e)}") from e
    except Exception as e:
        # Cleanup partially extracted files on any error
        if dest_path.exists():
            shutil.rmtree(dest_path, ignore_errors=True)
        raise e

    return ExtractionResult(
        project_id=project_id,
        target_dir=dest_path,
        extracted_files_count=extracted_count,
        skipped_files_count=skipped_count,
        total_uncompressed_bytes=total_bytes,
    )
