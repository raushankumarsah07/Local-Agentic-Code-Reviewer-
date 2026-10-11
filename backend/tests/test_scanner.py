"""
Unit tests for the repository scanner module (app/ingestion/scanner.py).
Tests language detection, line counting, directory walking, and ignore rules.
"""

from pathlib import Path
from app.ingestion.scanner import (
    count_file_lines,
    detect_language,
    scan_repository,
)


def test_detect_language_standard_extensions(temp_workspace: Path):
    """Verify correct language classification across various extensions."""
    test_cases = [
        ("app.py", "Python"),
        ("types.pyi", "Python"),
        ("index.js", "JavaScript"),
        ("Component.jsx", "JavaScript (JSX)"),
        ("service.ts", "TypeScript"),
        ("View.tsx", "TypeScript (TSX)"),
        ("index.html", "HTML"),
        ("styles.css", "CSS"),
        ("config.json", "JSON"),
        ("settings.yaml", "YAML"),
        ("cargo.toml", "TOML"),
        ("README.md", "Markdown"),
        ("notes.txt", "Plain Text"),
        ("schema.sql", "SQL"),
        ("deploy.sh", "Shell"),
        ("main.cpp", "C++"),
        ("server.go", "Go"),
        ("lib.rs", "Rust"),
        ("Dockerfile", "Dockerfile"),
        ("Makefile", "Makefile"),
    ]

    for filename, expected_lang in test_cases:
        p = temp_workspace / filename
        p.touch()
        assert detect_language(p) == expected_lang, f"Failed for {filename}"


def test_count_file_lines(temp_workspace: Path):
    """Verify line counting handles empty files, single lines, and multiple lines."""
    empty_file = temp_workspace / "empty.py"
    empty_file.write_text("", encoding="utf-8")
    assert count_file_lines(empty_file) == 0

    single_line = temp_workspace / "single.py"
    single_line.write_text("x = 42", encoding="utf-8")
    assert count_file_lines(single_line) == 1

    multi_line = temp_workspace / "multi.py"
    multi_line.write_text("def foo():\n    print(1)\n    return True\n", encoding="utf-8")
    assert count_file_lines(multi_line) == 3


def test_scan_repository_with_fixture(temp_workspace: Path):
    """
    Verify scan_repository properly counts files, aggregates lines, detects languages,
    and ignores .git, node_modules, venv, and binary assets.
    """
    repo_dir = temp_workspace / "sample_repo"
    repo_dir.mkdir()

    # Valid source files
    (repo_dir / "src").mkdir()
    (repo_dir / "src" / "main.py").write_text("import utils\nprint('hello')\n", encoding="utf-8")  # 2 lines
    (repo_dir / "src" / "utils.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")  # 2 lines

    (repo_dir / "docs").mkdir()
    (repo_dir / "docs" / "README.md").write_text("# Documentation\nDetails here.\nThird line.\n", encoding="utf-8")  # 3 lines

    (repo_dir / "package.json").write_text('{\n  "name": "demo"\n}\n', encoding="utf-8")  # 3 lines

    # Ignored directories and files
    (repo_dir / ".git").mkdir()
    (repo_dir / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

    (repo_dir / "node_modules" / "express").mkdir(parents=True)
    (repo_dir / "node_modules" / "express" / "index.js").write_text("module.exports = {};\n", encoding="utf-8")

    (repo_dir / "venv" / "bin").mkdir(parents=True)
    (repo_dir / "venv" / "bin" / "activate").write_text("# venv script\n", encoding="utf-8")

    (repo_dir / "__pycache__").mkdir()
    (repo_dir / "__pycache__" / "main.cpython-311.pyc").write_bytes(b"\x00\x01\x02\x03")

    (repo_dir / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    # Run scanner
    summary = scan_repository(repo_dir, "test_proj_1")

    # Only 4 valid source files should be detected
    assert summary.total_files == 4
    assert summary.total_lines == 10  # 2 + 2 + 3 + 3
    assert summary.languages == {
        "Python": 2,
        "Markdown": 1,
        "JSON": 1,
    }

    scanned_paths = [f.path for f in summary.files]
    assert scanned_paths == [
        "docs/README.md",
        "package.json",
        "src/main.py",
        "src/utils.py",
    ]


def test_scan_empty_directory(temp_workspace: Path):
    """Verify scanning an empty directory returns zero totals cleanly."""
    empty_dir = temp_workspace / "empty_repo"
    empty_dir.mkdir()
    summary = scan_repository(empty_dir, "empty_proj")
    assert summary.total_files == 0
    assert summary.total_lines == 0
    assert len(summary.files) == 0
