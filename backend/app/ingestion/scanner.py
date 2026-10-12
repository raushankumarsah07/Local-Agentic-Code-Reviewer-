"""
Repository scanner module.
Traverses project workspaces, enforces ignore rules, identifies programming languages,
and computes per-file metrics (path, size, line count).
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from app.ingestion.zip_handler import IGNORED_DIR_NAMES, IGNORED_EXTENSIONS, is_ignored_path


# Map of file extensions to canonical language identifiers
EXTENSION_LANGUAGE_MAP: Dict[str, str] = {
    # Python
    ".py": "Python",
    ".pyi": "Python",
    ".pyw": "Python",
    # JavaScript & TypeScript
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".jsx": "JavaScript (JSX)",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (TSX)",
    # Web & Styling
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "SASS",
    ".less": "LESS",
    # Configuration & Data Serialization
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".ini": "INI",
    ".cfg": "Config",
    ".xml": "XML",
    ".csv": "CSV",
    # Documentation
    ".md": "Markdown",
    ".markdown": "Markdown",
    ".rst": "reStructuredText",
    ".txt": "Plain Text",
    # Shell Scripting
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    # Database
    ".sql": "SQL",
    # Systems & Compiled Languages
    ".c": "C",
    ".h": "C Header",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++ Header",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".php": "PHP",
    ".rb": "Ruby",
}


@dataclass
class ScannedFile:
    """Metadata for an individual scanned file."""
    path: str              # Relative path from project root (e.g., 'src/main.py')
    language: str          # Detected language (e.g., 'Python', 'Markdown')
    size_bytes: int        # File size in bytes
    line_count: int        # Total lines in the file


@dataclass
class ScanSummary:
    """Aggregated scan summary for an entire repository."""
    project_id: str
    repo_path: Path
    files: List[ScannedFile] = field(default_factory=list)
    total_files: int = 0
    total_lines: int = 0
    total_size_bytes: int = 0
    languages: Dict[str, int] = field(default_factory=dict)


def is_binary_content(sample_bytes: bytes) -> bool:
    """
    Check if a byte sample contains null bytes, indicating a binary file.
    """
    return b"\x00" in sample_bytes


def detect_language(file_path: Path) -> str:
    """
    Determine programming or markup language from file extension.
    If the extension is not in the map, check if it is readable plain text.
    
    Args:
        file_path: Path to the target file.
        
    Returns:
        Canonical language name or 'Plain Text' / 'Other'.
    """
    suffix = file_path.suffix.lower()
    if suffix in EXTENSION_LANGUAGE_MAP:
        return EXTENSION_LANGUAGE_MAP[suffix]

    # Handle files with special well-known names (e.g., Dockerfile, Makefile, LICENSE)
    stem_lower = file_path.name.lower()
    if stem_lower == "dockerfile":
        return "Dockerfile"
    if stem_lower in ("makefile", "gnumakefile"):
        return "Makefile"
    if stem_lower in ("license", "copying"):
        return "Plain Text"

    # Quick heuristic check for plain text files without standard extensions
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            if chunk and not is_binary_content(chunk):
                return "Plain Text"
    except Exception:
        pass

    return "Other"


def count_file_lines(file_path: Path) -> int:
    """
    Safely count the number of lines in a text file.
    Handles encoding variations gracefully (UTF-8, Latin-1 fallback).
    
    Args:
        file_path: Path to the file.
        
    Returns:
        Number of lines in the file, or 0 if empty or unreadable.
    """
    try:
        # First attempt standard UTF-8 reading
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
            if not content:
                return 0
            return len(content.splitlines())
    except Exception:
        try:
            # Fallback to Latin-1
            with open(file_path, "r", encoding="latin-1", errors="replace") as f:
                content = f.read()
                if not content:
                    return 0
                return len(content.splitlines())
        except Exception:
            return 0


def scan_repository(repo_path: Path, project_id: str) -> ScanSummary:
    """
    Walk the repository directory tree, apply ignore filters,
    detect languages, and compute metrics for every valid file.
    
    Args:
        repo_path: Directory path of the unpacked repository.
        project_id: Project identifier.
        
    Returns:
        ScanSummary with complete list of ScannedFile items and aggregate metrics.
    """
    resolved_root = repo_path.resolve()
    summary = ScanSummary(project_id=project_id, repo_path=resolved_root)

    if not resolved_root.exists() or not resolved_root.is_dir():
        return summary

    for root, dirs, files in os.walk(resolved_root):
        # 1. Prune ignored directories in-place to avoid descending into them
        dirs[:] = [
            d for d in dirs
            if d.lower() not in IGNORED_DIR_NAMES and not d.lower().endswith(".egg-info")
        ]

        for filename in files:
            # Skip hidden OS files (e.g. .DS_Store, Thumbs.db)
            if filename.startswith(".DS_Store") or filename.startswith("Thumbs.db"):
                continue

            full_file_path = Path(root) / filename
            rel_path = full_file_path.relative_to(resolved_root).as_posix()

            # 2. Check if file matches ignored path or extension
            if is_ignored_path(rel_path):
                continue

            # Check for non-code binary extensions
            if full_file_path.suffix.lower() in IGNORED_EXTENSIONS:
                continue

            # 3. Quick binary check: check first 1024 bytes for null bytes
            try:
                with open(full_file_path, "rb") as bf:
                    first_bytes = bf.read(1024)
                    if is_binary_content(first_bytes):
                        continue
            except Exception:
                continue

            # 4. Gather file metrics
            try:
                size_bytes = full_file_path.stat().st_size
            except OSError:
                size_bytes = 0

            language = detect_language(full_file_path)
            lines = count_file_lines(full_file_path)

            scanned = ScannedFile(
                path=rel_path,
                language=language,
                size_bytes=size_bytes,
                line_count=lines,
            )

            summary.files.append(scanned)
            summary.total_files += 1
            summary.total_lines += lines
            summary.total_size_bytes += size_bytes
            summary.languages[language] = summary.languages.get(language, 0) + 1

    # Sort files alphabetically by path for consistent ordering
    summary.files.sort(key=lambda f: f.path)
    return summary
