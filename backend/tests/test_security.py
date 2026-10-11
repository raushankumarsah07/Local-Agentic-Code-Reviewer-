"""
Unit and integration tests for Phase 7d Security Analysis.
Tests Bandit integration, Semgrep handling, custom AST vulnerability rules
(hardcoded secrets, eval/exec, subprocess shell=True, SQL string concatenation,
insecure deserialization), severity normalization, and 'potential' labeling.
"""

import ast
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.analysis.security import (
    SecurityAnalyzer,
    SecurityASTVisitor,
    ensure_potential_label,
    mask_secret,
    normalize_severity,
    VALID_SEVERITIES,
)
from app.db import crud
from app.db.models import Project


def test_normalize_severity_and_potential_label():
    """Verify severity strings normalize to standard 5 levels and titles always include Potential."""
    assert normalize_severity("CRITICAL") == "Critical"
    assert normalize_severity("high") == "High"
    assert normalize_severity("ERROR") == "High"
    assert normalize_severity("medium") == "Medium"
    assert normalize_severity("WARN") == "Medium"
    assert normalize_severity("WARNING") == "Medium"
    assert normalize_severity("low") == "Low"
    assert normalize_severity("info") == "Info"
    assert normalize_severity("unknown_val") == "Medium"

    # Test Bandit promotion
    assert normalize_severity("MEDIUM", test_id="B307") == "Critical"
    assert normalize_severity("HIGH", test_id="B102") == "Critical"
    assert normalize_severity("MEDIUM", test_id="B301") == "Critical"
    assert normalize_severity("MEDIUM", test_id="B608") == "Critical"

    # Potential label
    assert ensure_potential_label("Hardcoded Secret") == "Potential Hardcoded Secret"
    assert ensure_potential_label("potential SQL Injection") == "potential SQL Injection"
    assert ensure_potential_label("Potential Arbitrary Code Execution") == "Potential Arbitrary Code Execution"


def test_mask_secret_helper():
    """Verify secrets are masked to prevent leaking credentials in findings and UI."""
    raw = "AKIA1234567890ABCDEF"
    masked = mask_secret(raw)
    assert masked.startswith("AKIA")
    assert masked.endswith("CDEF")
    assert "1234567890" not in masked
    assert "*" in masked

    short = "secret"
    assert mask_secret(short) == "********"


def test_ast_rule_hardcoded_secrets():
    """Verify custom AST rule flags deliberate hardcoded secrets while skipping benign code."""
    insecure_code = """
# Deliberately insecure credentials fixture
AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozG66jYBwQzP_NzQeS6Q0iX9n-M8W8nJp2Q1lK4XzA"
db_password = "super_secret_db_password_999!"
api_key = "sk-proj-1234567890abcdefghijklmnopqrstuvwxyz"
private_key = "-----BEGIN RSA PRIVATE KEY-----\\nMIIEowIBAAKCAQEA0...\\n-----END RSA PRIVATE KEY-----"

# Benign variables that must NOT be flagged
dummy_key = "YOUR_KEY_HERE"
config_path = "app/config.json"
counter = 42
empty_token = ""
"""
    analyzer = SecurityAnalyzer(enable_bandit=False, enable_semgrep=False)
    findings = analyzer.analyze_code(insecure_code, "insecure_secrets.py", "proj_test")

    secret_findings = [f for f in findings if "secret" in f["title"].lower() or "credential" in f["title"].lower() or "token" in f["title"].lower() or "key" in f["title"].lower()]
    assert len(secret_findings) >= 5

    # Check that each deliberate secret was flagged
    titles = [f["title"] for f in secret_findings]
    assert any("AWS Access Key" in t for t in titles)
    assert any("JSON Web Token" in t for t in titles)
    assert any("Private Key" in t for t in titles)
    assert any("db_password" in t for t in titles)
    assert any("api_key" in t for t in titles)

    # All titles start with Potential
    for f in findings:
        assert f["title"].startswith("Potential")
        assert f["severity"] in VALID_SEVERITIES

    # Check private key is Critical
    pk_finding = next(f for f in secret_findings if "Private Key" in f["title"])
    assert pk_finding["severity"] == "Critical"


def test_ast_rule_eval_and_exec():
    """Verify AST rule detects arbitrary code execution via eval() and exec()."""
    insecure_code = """
def run_dynamic(user_str):
    eval(user_str)
    exec("print('dynamic: ' + user_str)")
    import builtins
    builtins.eval(user_str)
"""
    analyzer = SecurityAnalyzer(enable_bandit=False, enable_semgrep=False)
    findings = analyzer.analyze_code(insecure_code, "eval_exec.py", "proj_test")

    assert len(findings) >= 3
    for f in findings:
        assert f["severity"] == "Critical"
        assert f["title"].startswith("Potential Arbitrary Code Execution")
        assert "eval" in f["evidence_snippet"] or "exec" in f["evidence_snippet"]


def test_ast_rule_subprocess_shell_true():
    """Verify AST rule detects subprocess executions with shell=True while allowing shell=False."""
    insecure_code = """
import subprocess
import os

def execute_cmd(user_arg):
    # Insecure shell calls
    subprocess.run(f"cat {user_arg}", shell=True)
    subprocess.Popen("rm -rf " + user_arg, shell=True)
    os.system("echo " + user_arg)

def safe_cmd(arg):
    # Safe list invocation
    subprocess.run(["cat", arg], shell=False)
    subprocess.run(["ls", "-la"])
"""
    analyzer = SecurityAnalyzer(enable_bandit=False, enable_semgrep=False)
    findings = analyzer.analyze_code(insecure_code, "proc.py", "proj_test")

    assert len(findings) == 3
    for f in findings:
        assert f["severity"] == "High"
        assert f["title"].startswith("Potential Command Injection")
        assert f["start_line"] in {7, 8, 9}


def test_ast_rule_sql_injection_string_concat():
    """Verify AST rule detects SQL queries constructed via string concatenation, formatting, or f-strings."""
    insecure_code = """
def fetch_user(cursor, db, uid, uname):
    # Insecure query calls
    cursor.execute("SELECT * FROM users WHERE id = " + uid)
    cursor.execute(f"SELECT * FROM users WHERE username = '{uname}'")
    cursor.execute("SELECT * FROM accounts WHERE id = '%s'" % uid)
    cursor.execute("SELECT * FROM logs WHERE id = {}".format(uid))
    query = "SELECT * FROM orders WHERE user_id = " + uid

def safe_fetch(cursor, uid):
    # Safe parameterized queries
    cursor.execute("SELECT * FROM users WHERE id = %s", (uid,))
    cursor.execute("SELECT * FROM users WHERE id = ?", [uid])
"""
    analyzer = SecurityAnalyzer(enable_bandit=False, enable_semgrep=False)
    findings = analyzer.analyze_code(insecure_code, "queries.py", "proj_test")

    assert len(findings) >= 5
    for f in findings:
        assert f["severity"] == "Critical"
        assert f["title"].startswith("Potential SQL Injection")
        # Line numbers correspond to the insecure executions and assignments
        assert f["start_line"] in {4, 5, 6, 7, 8}


def test_ast_rule_insecure_deserialization():
    """Verify AST rule detects unsafe pickle, PyYAML, marshal, and shelve deserialization."""
    insecure_code = """
import pickle
import yaml
import marshal
import shelve

def unpack(payload):
    d1 = pickle.loads(payload)
    d2 = marshal.loads(payload)
    d3 = yaml.load(payload)
    d4 = yaml.unsafe_load(payload)
    s = shelve.open("data.db")

def safe_unpack(payload):
    s1 = yaml.safe_load(payload)
    s2 = yaml.load(payload, Loader=yaml.SafeLoader)
"""
    analyzer = SecurityAnalyzer(enable_bandit=False, enable_semgrep=False)
    findings = analyzer.analyze_code(insecure_code, "deser.py", "proj_test")

    assert len(findings) >= 5
    for f in findings:
        assert f["severity"] == "Critical"
        assert f["title"].startswith("Potential Insecure Deserialization")
        assert f["start_line"] in {8, 9, 10, 11, 12}


def test_safe_file_zero_critical_or_high_findings():
    """Verify a clean, secure file produces no critical or high security findings."""
    clean_code = """
import subprocess
import yaml

def safe_math(a, b):
    return a + b

def safe_process():
    subprocess.run(["ls", "-la"], shell=False)

def safe_config(text):
    return yaml.safe_load(text)
"""
    analyzer = SecurityAnalyzer(enable_bandit=False, enable_semgrep=False)
    findings = analyzer.analyze_code(clean_code, "clean.py", "proj_test")
    severe_findings = [f for f in findings if f["severity"] in {"Critical", "High"}]
    assert len(severe_findings) == 0


def test_bandit_integration_and_project_scan(tmp_path: Path):
    """Verify complete SecurityAnalyzer scan runs Bandit and custom AST rules on disk fixtures."""
    repo_dir = tmp_path / "insecure_repo"
    repo_dir.mkdir()

    # Create deliberately insecure fixture file
    (repo_dir / "vuln_sample.py").write_text("""
import subprocess
import pickle

API_KEY = "AKIAIOSFODNN7EXAMPLE"

def execute_cmd(user_input):
    eval(user_input)
    subprocess.run("ls " + user_input, shell=True)
    pickle.loads(b"cos\\nsystem\\n(S'ls'\\ntR.")
""", encoding="utf-8")

    analyzer = SecurityAnalyzer(enable_bandit=True, enable_semgrep=True)
    findings = analyzer.analyze_project(repo_dir, "proj_integrated")

    assert len(findings) >= 4

    # Verify all severities are valid
    for f in findings:
        assert f["severity"] in VALID_SEVERITIES
        assert f["title"].startswith("Potential")
        assert f["file"] == "vuln_sample.py"
        assert f["type"] == "security"

    # Verify Bandit was integrated
    source_tools = [f["source_tool"] for f in findings]
    assert any("bandit" in s for s in source_tools)


def test_security_api_workflow(client: TestClient):
    """Integration test for POST /projects/{project_id}/analyze/security API endpoint."""
    import io
    import zipfile

    insecure_source = """
import subprocess

SECRET_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozG66jYBwQzP_NzQeS6Q0iX9n-M8W8nJp2Q1lK4XzA"

def handler(raw_code):
    eval(raw_code)
    subprocess.run(["cat", "/etc/hosts"], shell=True)
"""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("app.py", insecure_source)
    zip_buffer.seek(0)

    # 1. Upload project ZIP
    upload_res = client.post(
        "/projects/upload",
        files={"file": ("sec_repo.zip", zip_buffer, "application/zip")},
    )
    assert upload_res.status_code == 201
    project_id = upload_res.json()["project_id"]

    # 2. Trigger security analysis
    res = client.post(f"/projects/{project_id}/analyze/security")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["project_id"] == project_id
    assert data["total_findings"] >= 3
    assert data["critical_count"] >= 1  # eval()
    assert data["high_count"] >= 1      # JWT or shell=True
    assert len(data["findings"]) == data["total_findings"]

    # Verify all findings start with Potential
    for finding in data["findings"]:
        assert finding["title"].startswith("Potential")
        assert finding["severity"] in VALID_SEVERITIES
        assert finding["type"] == "security"

    # 3. Query findings via GET /projects/{id}/findings?type=security
    get_res = client.get(f"/projects/{project_id}/findings?type=security")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["total"] == data["total_findings"]

    # 4. Query findings summary
    sum_res = client.get(f"/projects/{project_id}/findings/summary")
    assert sum_res.status_code == 200
    sum_data = sum_res.json()
    assert sum_data["total"] >= 3
    assert "security" in sum_data["by_type"]
    assert sum_data["by_type"]["security"] == data["total_findings"]
