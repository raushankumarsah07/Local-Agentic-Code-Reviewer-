"""
Tests for Phase 7a: Finding Data Model and Complexity Analyzer.
Verifies McCabe cyclomatic complexity calculation, long-function detection,
configurable thresholds, database persistence, and REST endpoints.
"""

import io
import zipfile
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.analysis.complexity import (
    ComplexityAnalyzer,
    ComplexityThresholds,
    ASTCyclomaticComplexityVisitor,
)
from app.db import crud
from app.db.models import Finding
from app.main import app


# --- Test Code Fixtures ---

SIMPLE_CODE = """
def simple_add(a, b):
    # Base complexity = 1
    return a + b
"""

COMPLEX_CODE = """
def complex_decision_maker(val, flag, items):
    # Cyclomatic complexity should be > 10
    total = 0
    if val > 100:                  # +1
        total += 1
    elif val > 50:                 # +1
        total += 2
    elif val > 0:                  # +1
        total += 3
    else:
        total += 4

    if flag and len(items) > 0:    # +2 (if + and)
        for item in items:         # +1
            if item.is_valid():    # +1
                total += item.score
            elif item.is_pending():# +1
                total += 1
    
    while total < 20:              # +1
        total += 2

    try:                           # 0
        total = total / val
    except ZeroDivisionError:      # +1
        total = 0
    except ValueError:             # +1
        total = -1

    assert total >= 0              # +1
    return total
"""

LONG_FUNCTION_CODE = """
def very_long_function():
""" + "\n".join([f"    x_{i} = {i} + 1" for i in range(60)]) + """
    return x_59
"""


def test_ast_cyclomatic_complexity_calculation():
    """Verify cyclomatic complexity counts decision points accurately."""
    analyzer = ComplexityAnalyzer(thresholds=ComplexityThresholds(complexity_warning_threshold=5))
    metrics = analyzer._extract_function_metrics(COMPLEX_CODE)
    
    assert len(metrics) == 1
    fn = metrics[0]
    assert fn["name"] == "complex_decision_maker"
    # Expected complexity is >= 10
    assert fn["complexity"] >= 10


def test_simple_function_no_findings():
    """A function with CC = 1 should not generate any warnings under default thresholds."""
    analyzer = ComplexityAnalyzer()
    findings = analyzer.analyze_code(SIMPLE_CODE, "simple.py", "proj_test")
    assert len(findings) == 0


def test_high_complexity_generates_finding():
    """A function exceeding the warning threshold should generate a complexity finding."""
    analyzer = ComplexityAnalyzer(thresholds=ComplexityThresholds(complexity_warning_threshold=8))
    findings = analyzer.analyze_code(COMPLEX_CODE, "complex.py", "proj_test")

    assert len(findings) >= 1
    f = findings[0]
    assert f["type"] == "complexity"
    assert f["source_tool"] == "mccabe"
    assert "High Cyclomatic Complexity" in f["title"]
    assert f["file"] == "complex.py"
    assert f["start_line"] == 2
    assert f["severity"] in ("Medium", "High", "Critical")
    assert "refactor" in f["explanation"].lower() or "branches" in f["explanation"].lower()


def test_long_function_generates_finding():
    """Functions exceeding line threshold should generate a long-function finding."""
    analyzer = ComplexityAnalyzer(
        thresholds=ComplexityThresholds(
            complexity_warning_threshold=50,
            long_function_warning_lines=40,
            long_function_critical_lines=80,
        )
    )
    findings = analyzer.analyze_code(LONG_FUNCTION_CODE, "long.py", "proj_test")

    assert len(findings) == 1
    f = findings[0]
    assert f["type"] == "complexity"
    assert f["source_tool"] == "complexity_analyzer"
    assert "Long Function" in f["title"]
    assert f["severity"] == "Medium"
    assert "6" in f["title"]  # ~62 lines


def test_configurable_thresholds_customization():
    """Test that custom thresholds strictly control when findings are triggered."""
    # Stricter thresholds (threshold = 2)
    strict_analyzer = ComplexityAnalyzer(
        thresholds=ComplexityThresholds(complexity_warning_threshold=2)
    )
    code_with_one_branch = """
def check_positive(x):
    if x > 0:
        return True
    return False
"""
    strict_findings = strict_analyzer.analyze_code(code_with_one_branch, "check.py", "proj_test")
    assert len(strict_findings) == 1

    # Permissive thresholds (threshold = 20)
    permissive_analyzer = ComplexityAnalyzer(
        thresholds=ComplexityThresholds(complexity_warning_threshold=20)
    )
    permissive_findings = permissive_analyzer.analyze_code(code_with_one_branch, "check.py", "proj_test")
    assert len(permissive_findings) == 0


def test_unparsable_file_skipped_without_crash():
    """Syntax error files should return zero findings without throwing exceptions."""
    broken_code = "def broken(::: syntax error"
    analyzer = ComplexityAnalyzer()
    findings = analyzer.analyze_code(broken_code, "broken.py", "proj_test")
    assert findings == []


# --- API Endpoints Integration Tests ---

def test_complexity_api_workflow(client: TestClient):
    """End-to-end test of project upload, complexity analysis trigger, findings listing, and summary."""
    # 1. Create a zip with one simple and one complex file
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("simple.py", SIMPLE_CODE)
        zf.writestr("complex.py", COMPLEX_CODE)
        zf.writestr("long.py", LONG_FUNCTION_CODE)
    zip_buffer.seek(0)

    # 2. Upload zip
    upload_res = client.post(
        "/projects/upload",
        files={"file": ("test_complexity_repo.zip", zip_buffer, "application/zip")},
    )
    assert upload_res.status_code == 201
    project_id = upload_res.json()["project_id"]

    # 3. Trigger complexity analysis with custom thresholds
    analyze_res = client.post(
        f"/projects/{project_id}/analyze/complexity",
        json={
            "complexity_warning_threshold": 5,
            "complexity_critical_threshold": 12,
            "long_function_warning_lines": 40,
            "long_function_critical_lines": 80,
        },
    )
    assert analyze_res.status_code == 200
    analyze_data = analyze_res.json()
    assert analyze_data["findings_count"] >= 2
    assert len(analyze_data["findings"]) >= 2

    # 4. List all findings for project
    list_res = client.get(f"/projects/{project_id}/findings")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 2
    assert list_data["count"] >= 2

    # 5. Filter findings by file
    complex_file_res = client.get(f"/projects/{project_id}/findings?file=complex.py")
    assert complex_file_res.status_code == 200
    complex_findings = complex_file_res.json()["findings"]
    assert len(complex_findings) >= 1
    assert all(f["file"] == "complex.py" for f in complex_findings)

    # 6. Fetch findings summary
    summary_res = client.get(f"/projects/{project_id}/findings/summary")
    assert summary_res.status_code == 200
    summary_data = summary_res.json()
    assert summary_data["total"] >= 2
    assert "complexity" in summary_data["by_type"]

    # 7. Delete findings
    delete_res = client.delete(f"/projects/{project_id}/findings")
    assert delete_res.status_code == 200

    # 8. Verify findings cleared
    recheck_res = client.get(f"/projects/{project_id}/findings")
    assert recheck_res.json()["total"] == 0
