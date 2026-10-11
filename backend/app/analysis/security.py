"""
Security Static Analyzer and Vulnerability Scanner.
Combines Bandit, Semgrep (if available), and custom AST-level rules for:
1. Hardcoded secrets (API keys, AWS credentials, JWT tokens, unencrypted private keys, passwords)
2. eval() and exec() arbitrary code execution
3. subprocess invocations with shell=True
4. SQL queries constructed via string concatenation, formatting, or f-strings
5. Insecure deserialization (pickle, unsafe PyYAML, marshal, shelve)

Normalizes all severities to Critical, High, Medium, Low, Info.
Labels all findings as "potential" to maintain analytical and review integrity.
"""

import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Standardized Severity Levels
VALID_SEVERITIES = {"Critical", "High", "Medium", "Low", "Info"}

# Severity Hierarchy for Ranking and Deduplication
SEVERITY_ORDER: Dict[str, int] = {
    "Critical": 4,
    "High": 3,
    "Medium": 2,
    "Low": 1,
    "Info": 0,
}

# Regex Patterns for Hardcoded Secrets
AWS_KEY_REGEX = re.compile(r"AKIA[0-9A-Z]{16}")
JWT_REGEX = re.compile(r"ey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
PRIVATE_KEY_REGEX = re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")
SECRET_VAR_REGEX = re.compile(
    r"^(?:.*_)?(api_?key|secret|token|password|passwd|auth_?token|access_?token|private_?key|client_?secret|credentials?)(?:_.*)?$",
    re.IGNORECASE,
)

# Common Benign Placeholders to Avoid False Positives
SECRET_PLACEHOLDERS = {
    "TODO", "CHANGE_ME", "CHANGEME", "YOUR_KEY_HERE", "YOUR_API_KEY",
    "DUMMY", "TEST", "EXAMPLE", "PLACEHOLDER", "LOCALHOST", "127.0.0.1",
    "NONE", "NULL", "UNDEFINED", "PASSWORD", "ADMIN", "ROOT", "ENV",
    "SECRET", "TOKEN", "BEARER", "TRUE", "FALSE", "UNKNOWN"
}

# Regex for SQL Keywords in String Literals
SQL_COMMAND_REGEX = re.compile(
    r"\b(SELECT\s+.*?\s+FROM|INSERT\s+INTO\s+|UPDATE\s+.*?\s+SET|DELETE\s+FROM\s+|DROP\s+TABLE\s+|CREATE\s+TABLE\s+|ALTER\s+TABLE\s+)\b",
    re.IGNORECASE,
)
SQL_VAR_NAME_REGEX = re.compile(
    r"^(?:.*_)?(sql|query|stmt|statement|command|raw_sql|sql_query)(?:_.*)?$",
    re.IGNORECASE,
)


def normalize_severity(severity: str, test_id: Optional[str] = None) -> str:
    """
    Normalize any severity string to one of Critical, High, Medium, Low, Info.
    Promotes high-impact vulnerability identifiers (e.g., Bandit B102, B301, B307) to Critical.
    """
    if test_id in {"B102", "B301", "B302", "B307", "B608"}:
        return "Critical"

    s = (severity or "").strip().lower()
    if s in {"critical", "fatal"}:
        return "Critical"
    elif s in {"high", "error"}:
        return "High"
    elif s in {"medium", "med", "warning", "warn"}:
        return "Medium"
    elif s in {"low", "minor"}:
        return "Low"
    elif s in {"info", "informational", "note"}:
        return "Info"
    return "Medium"


def ensure_potential_label(title: str) -> str:
    """
    Ensure every security finding title explicitly starts with 'Potential'.
    """
    cleaned = title.strip()
    if not cleaned.lower().startswith("potential"):
        return f"Potential {cleaned}"
    return cleaned


def mask_secret(secret: str) -> str:
    """
    Mask sensitive secrets for safe evidence display.
    Example: AKIA1234567890ABCDEF -> AKIA************CDEF
    """
    clean = secret.strip()
    if len(clean) <= 8:
        return "********"
    visible_prefix = clean[:4]
    visible_suffix = clean[-4:]
    masked_middle = "*" * max(4, len(clean) - 8)
    return f"{visible_prefix}{masked_middle}{visible_suffix}"


class SecurityASTVisitor(ast.NodeVisitor):
    """
    AST Visitor to detect custom security vulnerabilities:
    - Hardcoded secrets
    - eval() and exec()
    - subprocess with shell=True
    - SQL built by string concatenation / formatting
    - Insecure deserialization
    """

    def __init__(self, code: str, rel_path: str, project_id: str):
        self.code = code
        self.lines = code.splitlines()
        self.rel_path = rel_path
        self.project_id = project_id
        self.findings: List[Dict[str, Any]] = []
        self._reported_keys: Set[Tuple[int, str]] = set()

    def _get_snippet(self, lineno: int, mask_target: Optional[str] = None) -> str:
        """Fetch code line snippet at line number with optional secret masking."""
        if 1 <= lineno <= len(self.lines):
            raw = self.lines[lineno - 1].strip()
            if mask_target and mask_target in raw:
                raw = raw.replace(mask_target, mask_secret(mask_target))
            return raw
        return ""

    def _get_call_name(self, func_node: ast.AST) -> str:
        """Extract a readable string name for a call function node."""
        if isinstance(func_node, ast.Name):
            return func_node.id
        elif isinstance(func_node, ast.Attribute):
            val_id = getattr(func_node.value, "id", "")
            return f"{val_id}.{func_node.attr}" if val_id else func_node.attr
        return "call"

    def _add_finding(
        self,
        category: str,
        severity: str,
        title: str,
        start_line: int,
        end_line: int,
        evidence: str,
        explanation: str,
    ):
        """Register a unique normalized security finding."""
        key = (start_line, category)
        if key in self._reported_keys:
            return
        self._reported_keys.add(key)

        self.findings.append({
            "project_id": self.project_id,
            "type": "security",
            "severity": normalize_severity(severity),
            "title": ensure_potential_label(title),
            "file": self.rel_path,
            "start_line": start_line,
            "end_line": max(start_line, end_line),
            "evidence_snippet": evidence,
            "source_tool": "ast_security_rules",
            "explanation": explanation,
        })

    def _is_dangerous_sql_expression(self, expr: ast.AST, var_name: str = "") -> bool:
        """Check if an expression dynamically composes SQL using concatenation, f-string, or format."""
        is_formatted_expr = False
        if isinstance(expr, ast.BinOp) and isinstance(expr.op, (ast.Add, ast.Mod)):
            is_formatted_expr = True
        elif isinstance(expr, ast.JoinedStr):
            is_formatted_expr = True
        elif isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr == "format":
            is_formatted_expr = True

        if not is_formatted_expr:
            return False

        # If variable name indicates SQL
        if var_name and SQL_VAR_NAME_REGEX.search(var_name):
            return True

        # Check if any literal part in the expression matches SQL keywords
        for child in ast.walk(expr):
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                if SQL_COMMAND_REGEX.search(child.value) or (
                    "SELECT " in child.value.upper() and "FROM " in child.value.upper()
                ):
                    return True

        return False

    def visit_Call(self, node: ast.Call):
        start_line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", start_line)
        func_name = self._get_call_name(node.func)

        # Rule 1: eval() and exec()
        if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
            self._add_finding(
                category="eval_exec",
                severity="Critical",
                title=f"Potential Arbitrary Code Execution: Use of '{node.func.id}()'",
                start_line=start_line,
                end_line=end_line,
                evidence=self._get_snippet(start_line),
                explanation=(
                    f"Calling '{node.func.id}()' dynamically parses and executes arbitrary Python code. "
                    "If unvalidated or external input reaches this invocation, attackers can execute "
                    "arbitrary system commands with the privileges of the running process. "
                    "Marked as 'potential' pending verification of argument origin."
                ),
            )
        elif isinstance(node.func, ast.Attribute) and node.func.attr in {"eval", "exec"}:
            val_id = getattr(node.func.value, "id", "")
            if val_id in {"builtins", "__builtin__", ""}:
                self._add_finding(
                    category="eval_exec",
                    severity="Critical",
                    title=f"Potential Arbitrary Code Execution: Use of '{func_name}()'",
                    start_line=start_line,
                    end_line=end_line,
                    evidence=self._get_snippet(start_line),
                    explanation=(
                        f"Dynamic code execution via '{func_name}()' introduces severe remote code execution risk. "
                        "Marked as 'potential' pending review of call inputs."
                    ),
                )

        # Rule 2: subprocess with shell=True
        has_shell_true = False
        for kw in node.keywords:
            if kw.arg == "shell":
                if isinstance(kw.value, ast.Constant) and bool(kw.value.value) is True:
                    has_shell_true = True
                elif isinstance(kw.value, ast.Name) and kw.value.id == "True":
                    has_shell_true = True

        is_os_shell = False
        if isinstance(node.func, ast.Attribute):
            val_id = getattr(node.func.value, "id", "")
            if val_id == "os" and node.func.attr in {"system", "popen"}:
                is_os_shell = True

        if has_shell_true or is_os_shell:
            title = (
                f"Potential Command Injection: Process execution with shell=True ({func_name})"
                if has_shell_true
                else f"Potential Command Injection: Direct shell execution via '{func_name}()'"
            )
            self._add_finding(
                category="subprocess_shell",
                severity="High",
                title=title,
                start_line=start_line,
                end_line=end_line,
                evidence=self._get_snippet(start_line),
                explanation=(
                    f"Invoking '{func_name}' with shell=True spawns an underlying system shell (/bin/sh or cmd.exe) "
                    "to interpret the command string. If arguments contain unsanitized user inputs or concatenations, "
                    "attackers can inject arbitrary shell commands. Marked as 'potential'."
                ),
            )

        # Rule 3: SQL built by string concatenation / formatting inside execute calls
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"execute", "raw", "executemany"}:
            if node.args and self._is_dangerous_sql_expression(node.args[0]):
                self._add_finding(
                    category="sql_concatenation",
                    severity="Critical",
                    title=f"Potential SQL Injection: Database '{node.func.attr}()' with dynamic string formatting",
                    start_line=start_line,
                    end_line=end_line,
                    evidence=self._get_snippet(start_line),
                    explanation=(
                        f"Database execution function '{node.func.attr}()' received a dynamically constructed query "
                        "using string concatenation (+), percent formatting (%), or an f-string. This bypasses prepared "
                        "statement parameter bindings and exposes the database to SQL injection attacks. "
                        "Marked as 'potential' pending inspection of query parameters."
                    ),
                )

        # Rule 4: Insecure deserialization
        if isinstance(node.func, ast.Attribute):
            val_id = getattr(node.func.value, "id", "")
            method_name = node.func.attr

            # pickle / _pickle / cPickle
            if val_id in {"pickle", "_pickle", "cPickle"} and method_name in {"loads", "load"}:
                self._add_finding(
                    category="insecure_deserialization",
                    severity="Critical",
                    title=f"Potential Insecure Deserialization: Dangerous object load via '{val_id}.{method_name}()'",
                    start_line=start_line,
                    end_line=end_line,
                    evidence=self._get_snippet(start_line),
                    explanation=(
                        f"Deserializing untrusted data with '{val_id}.{method_name}()' can instantiate arbitrary "
                        "Python classes and execute arbitrary bytecode during object reconstruction. "
                        "Marked as 'potential' pending verification of data provenance."
                    ),
                )
            # marshal
            elif val_id == "marshal" and method_name in {"loads", "load"}:
                self._add_finding(
                    category="insecure_deserialization",
                    severity="Critical",
                    title=f"Potential Insecure Deserialization: Dangerous unpack via 'marshal.{method_name}()'",
                    start_line=start_line,
                    end_line=end_line,
                    evidence=self._get_snippet(start_line),
                    explanation=(
                        f"Deserializing bytecode or structures with 'marshal.{method_name}()' can cause memory "
                        "corruption or arbitrary code execution if inputs are untrusted. Marked as 'potential'."
                    ),
                )
            # shelve
            elif val_id == "shelve" and method_name == "open":
                self._add_finding(
                    category="insecure_deserialization",
                    severity="Critical",
                    title="Potential Insecure Deserialization: Unsafe persistent storage via 'shelve.open()'",
                    start_line=start_line,
                    end_line=end_line,
                    evidence=self._get_snippet(start_line),
                    explanation=(
                        "The 'shelve' module relies on pickle for object serialization. Opening an untrusted shelf file "
                        "can trigger arbitrary code execution. Marked as 'potential'."
                    ),
                )
            # PyYAML
            elif val_id == "yaml":
                if method_name == "unsafe_load":
                    self._add_finding(
                        category="insecure_deserialization",
                        severity="Critical",
                        title="Potential Insecure Deserialization: PyYAML unsafe_load() invoked",
                        start_line=start_line,
                        end_line=end_line,
                        evidence=self._get_snippet(start_line),
                        explanation=(
                            "Invoking 'yaml.unsafe_load()' allows arbitrary Python object instantiation and code execution. "
                            "Marked as 'potential'."
                        ),
                    )
                elif method_name == "load":
                    # Check Loader keyword
                    loader_kw = next((kw for kw in node.keywords if kw.arg == "Loader"), None)
                    is_safe = False
                    if loader_kw:
                        loader_repr = self._get_call_name(loader_kw.value)
                        if "SafeLoader" in loader_repr or "CSafeLoader" in loader_repr:
                            is_safe = True

                    if not is_safe:
                        self._add_finding(
                            category="insecure_deserialization",
                            severity="Critical",
                            title="Potential Insecure Deserialization: PyYAML load() invoked without SafeLoader",
                            start_line=start_line,
                            end_line=end_line,
                            evidence=self._get_snippet(start_line),
                            explanation=(
                                "Calling 'yaml.load()' without 'Loader=yaml.SafeLoader' (or CSafeLoader) allows YAML tags "
                                "like !!python/object/apply to execute arbitrary Python code. Marked as 'potential'."
                            ),
                        )

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        self._check_assignment(node.targets, node.value, getattr(node, "lineno", 1), getattr(node, "end_lineno", 1))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if node.value:
            self._check_assignment([node.target], node.value, getattr(node, "lineno", 1), getattr(node, "end_lineno", 1))
        self.generic_visit(node)

    def _check_assignment(self, targets: List[ast.AST], value: ast.AST, start_line: int, end_line: int):
        """Check variable assignments for hardcoded secrets and SQL string concatenation."""
        target_names: List[str] = []
        for t in targets:
            if isinstance(t, ast.Name):
                target_names.append(t.id)
            elif isinstance(t, ast.Attribute):
                target_names.append(t.attr)

        primary_target = target_names[0] if target_names else ""

        # Check SQL constructed via assignment: query = "SELECT ... " + x
        if self._is_dangerous_sql_expression(value, primary_target):
            self._add_finding(
                category="sql_concatenation",
                severity="Critical",
                title=f"Potential SQL Injection: SQL statement constructed dynamically in '{primary_target}'",
                start_line=start_line,
                end_line=end_line,
                evidence=self._get_snippet(start_line),
                explanation=(
                    f"Variable '{primary_target}' is constructed dynamically using string concatenation, "
                    "f-strings, or percent formatting with SQL syntax. If passed to a query executor, "
                    "it creates severe SQL injection vulnerabilities. Marked as 'potential'."
                ),
            )

        # Check Hardcoded Secrets
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            str_val = value.value.strip()

            # 1. Unencrypted Private Key
            if PRIVATE_KEY_REGEX.search(str_val):
                self._add_finding(
                    category="hardcoded_secret",
                    severity="Critical",
                    title="Potential Hardcoded Secret: Unencrypted Private Key detected",
                    start_line=start_line,
                    end_line=end_line,
                    evidence=self._get_snippet(start_line, mask_target=str_val),
                    explanation=(
                        "An unencrypted private key header was found hardcoded in the source file. "
                        "Private keys must never be committed to source repositories. Marked as 'potential'."
                    ),
                )
                return

            # 2. AWS Access Key ID
            if AWS_KEY_REGEX.search(str_val):
                self._add_finding(
                    category="hardcoded_secret",
                    severity="High",
                    title="Potential Hardcoded Secret: AWS Access Key ID detected",
                    start_line=start_line,
                    end_line=end_line,
                    evidence=self._get_snippet(start_line, mask_target=str_val),
                    explanation=(
                        "A potential AWS Access Key ID matching 'AKIA...' was detected in a string assignment. "
                        "Credentials must be loaded via environment variables or secret managers. Marked as 'potential'."
                    ),
                )
                return

            # 3. JSON Web Token (JWT)
            if JWT_REGEX.search(str_val):
                self._add_finding(
                    category="hardcoded_secret",
                    severity="High",
                    title="Potential Hardcoded Secret: JSON Web Token (JWT) detected",
                    start_line=start_line,
                    end_line=end_line,
                    evidence=self._get_snippet(start_line, mask_target=str_val),
                    explanation=(
                        "A potential JSON Web Token (JWT) was found assigned directly in the code. "
                        "Hardcoded tokens can grant unauthorized API access. Marked as 'potential'."
                    ),
                )
                return

            # 4. Sensitive variable name check
            for t_name in target_names:
                if SECRET_VAR_REGEX.search(t_name):
                    # Filter out benign placeholders
                    if str_val.upper() in SECRET_PLACEHOLDERS:
                        continue
                    if len(str_val) < 6:
                        continue
                    if str_val.startswith(("http://", "https://", "/", "./", "../")) or str_val.endswith((".py", ".json", ".txt")):
                        continue

                    severity = "High" if len(str_val) >= 20 else "Medium"
                    self._add_finding(
                        category="hardcoded_secret",
                        severity=severity,
                        title=f"Potential Hardcoded Secret: Sensitive credential in '{t_name}'",
                        start_line=start_line,
                        end_line=end_line,
                        evidence=self._get_snippet(start_line, mask_target=str_val),
                        explanation=(
                            f"Variable '{t_name}' contains a hardcoded credential or token value. "
                            "Hardcoded credentials risk unauthorized disclosure when code is shared or audited. "
                            "Marked as 'potential' pending confirmation."
                        ),
                    )
                    break

    def visit_Constant(self, node: ast.Constant):
        """Catch standalone secrets in dictionary values, tuples, or function arguments."""
        if isinstance(node.value, str):
            str_val = node.value.strip()
            start_line = getattr(node, "lineno", 1)
            end_line = getattr(node, "end_lineno", start_line)

            if PRIVATE_KEY_REGEX.search(str_val):
                self._add_finding(
                    category="hardcoded_secret",
                    severity="Critical",
                    title="Potential Hardcoded Secret: Unencrypted Private Key detected",
                    start_line=start_line,
                    end_line=end_line,
                    evidence=self._get_snippet(start_line, mask_target=str_val),
                    explanation="An unencrypted private key was detected. Marked as 'potential'.",
                )
            elif AWS_KEY_REGEX.search(str_val):
                self._add_finding(
                    category="hardcoded_secret",
                    severity="High",
                    title="Potential Hardcoded Secret: AWS Access Key ID detected",
                    start_line=start_line,
                    end_line=end_line,
                    evidence=self._get_snippet(start_line, mask_target=str_val),
                    explanation="An AWS Access Key ID was detected in code. Marked as 'potential'.",
                )
            elif JWT_REGEX.search(str_val):
                self._add_finding(
                    category="hardcoded_secret",
                    severity="High",
                    title="Potential Hardcoded Secret: JSON Web Token (JWT) detected",
                    start_line=start_line,
                    end_line=end_line,
                    evidence=self._get_snippet(start_line, mask_target=str_val),
                    explanation="A JSON Web Token (JWT) was detected in code. Marked as 'potential'.",
                )
        self.generic_visit(node)


class SecurityAnalyzer:
    """
    Comprehensive Security Static Analyzer combining Bandit, Semgrep (if available),
    and custom AST vulnerability detection rules.
    """

    def __init__(self, enable_bandit: bool = True, enable_semgrep: bool = True):
        self.enable_bandit = enable_bandit
        self.enable_semgrep = enable_semgrep

    def analyze_code(self, code: str, rel_path: str, project_id: str) -> List[Dict[str, Any]]:
        """Run custom AST security visitor on a single code string."""
        try:
            tree = ast.parse(code)
            visitor = SecurityASTVisitor(code, rel_path, project_id)
            visitor.visit(tree)
            return visitor.findings
        except SyntaxError:
            # Unparsable files cannot trigger AST rules; pipeline must not crash
            return []

    def analyze_file(self, file_path: Path, project_root: Path, project_id: str) -> List[Dict[str, Any]]:
        """Analyze a single Python file on disk using custom AST rules."""
        try:
            rel_path = file_path.relative_to(project_root).as_posix()
        except ValueError:
            rel_path = file_path.name

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return self.analyze_code(content, rel_path, project_id)
        except Exception:
            return []

    def scan_ast_rules(self, project_root: Path, project_id: str) -> List[Dict[str, Any]]:
        """Traverse the project directory and run custom AST rules on all Python files."""
        findings: List[Dict[str, Any]] = []
        ignore_dirs = {
            "node_modules", ".git", ".venv", "venv", "__pycache__",
            ".pytest_cache", "build", "dist", ".idea", ".vscode"
        }

        for path in project_root.rglob("*.py"):
            if not path.is_file():
                continue
            if any(part in ignore_dirs or part.startswith(".") for part in path.parts):
                continue
            file_findings = self.analyze_file(path, project_root, project_id)
            findings.extend(file_findings)

        return findings

    def run_bandit(self, project_root: Path, project_id: str) -> List[Dict[str, Any]]:
        """
        Run Bandit static security analyzer via subprocess and normalize findings.
        Returns empty list gracefully if Bandit is unavailable or errors.
        """
        findings: List[Dict[str, Any]] = []
        if not self.enable_bandit:
            return findings

        try:
            cmd = [
                sys.executable,
                "-m",
                "bandit",
                "-r",
                str(project_root),
                "-f",
                "json",
                "-q",
                "--exit-zero",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if proc.stdout:
                try:
                    data = json.loads(proc.stdout)
                    for item in data.get("results", []):
                        test_id = item.get("test_id", "")
                        raw_file = item.get("filename", "")
                        try:
                            rel_file = Path(raw_file).relative_to(project_root).as_posix()
                        except Exception:
                            rel_file = Path(raw_file).name

                        raw_sev = item.get("issue_severity", "MEDIUM")
                        sev = normalize_severity(raw_sev, test_id=test_id)
                        issue_text = item.get("issue_text", "Security vulnerability")
                        start_line = item.get("line_number", 1)
                        line_range = item.get("line_range", [start_line])
                        end_line = max(line_range) if line_range else start_line

                        findings.append({
                            "project_id": project_id,
                            "type": "security",
                            "severity": sev,
                            "title": ensure_potential_label(f"Security Vulnerability: {issue_text} ({test_id})"),
                            "file": rel_file,
                            "start_line": start_line,
                            "end_line": end_line,
                            "evidence_snippet": item.get("code", "").strip(),
                            "source_tool": "bandit",
                            "explanation": (
                                f"Bandit security analyzer identified test {test_id}: {issue_text}. "
                                f"Normalized severity: {sev}, Confidence: {item.get('issue_confidence', 'UNKNOWN')}. "
                                "Marked as 'potential' pending code review."
                            ),
                        })
                except json.JSONDecodeError:
                    pass
        except Exception:
            # Bandit execution failures must not break the overall pipeline
            pass

        return findings

    def run_semgrep(self, project_root: Path, project_id: str) -> List[Dict[str, Any]]:
        """
        Run Semgrep security analyzer if installed in environment PATH.
        Returns empty list gracefully if Semgrep is unavailable.
        """
        findings: List[Dict[str, Any]] = []
        if not self.enable_semgrep:
            return findings

        semgrep_bin = shutil.which("semgrep")
        if not semgrep_bin:
            return findings

        try:
            cmd = [
                semgrep_bin,
                "scan",
                "--json",
                "--quiet",
                "--config",
                "auto",
                str(project_root),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if proc.stdout:
                try:
                    data = json.loads(proc.stdout)
                    for item in data.get("results", []):
                        check_id = item.get("check_id", "semgrep-rule")
                        path_str = item.get("path", "")
                        try:
                            rel_file = Path(path_str).relative_to(project_root).as_posix()
                        except Exception:
                            rel_file = Path(path_str).name

                        extra = item.get("extra", {})
                        raw_sev = extra.get("severity", "WARNING")
                        sev = normalize_severity(raw_sev)
                        start_line = item.get("start", {}).get("line", 1)
                        end_line = item.get("end", {}).get("line", start_line)
                        message = extra.get("message", "Semgrep security finding")

                        findings.append({
                            "project_id": project_id,
                            "type": "security",
                            "severity": sev,
                            "title": ensure_potential_label(f"Security Vulnerability: {check_id}"),
                            "file": rel_file,
                            "start_line": start_line,
                            "end_line": end_line,
                            "evidence_snippet": extra.get("lines", "").strip(),
                            "source_tool": "semgrep",
                            "explanation": (
                                f"Semgrep analyzer flagged rule '{check_id}': {message}. "
                                "Marked as 'potential' pending architectural review."
                            ),
                        })
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass

        return findings

    def analyze_project(self, project_root: Path, project_id: str) -> List[Dict[str, Any]]:
        """
        Perform complete security analysis of project:
        1. Run custom AST rules
        2. Run Bandit (if enabled)
        3. Run Semgrep (if enabled and available)
        4. Normalize severities, label as 'potential', and merge/deduplicate findings.
        """
        if not project_root.exists() or not project_root.is_dir():
            return []

        ast_findings = self.scan_ast_rules(project_root, project_id)
        bandit_findings = self.run_bandit(project_root, project_id)
        semgrep_findings = self.run_semgrep(project_root, project_id)

        # Merge and deduplicate by (file, start_line)
        merged: Dict[Tuple[str, int], Dict[str, Any]] = {}

        # 1. Register custom AST findings
        for f in ast_findings:
            key = (f["file"], f["start_line"])
            merged[key] = f

        # 2. Merge Bandit findings
        for bf in bandit_findings:
            key = (bf["file"], bf["start_line"])
            if key in merged:
                existing = merged[key]
                existing["source_tool"] = f"{existing['source_tool']} + bandit"
                # Elevate severity if Bandit has higher rank
                if SEVERITY_ORDER.get(bf["severity"], 0) > SEVERITY_ORDER.get(existing["severity"], 0):
                    existing["severity"] = bf["severity"]
                existing["explanation"] += f" Also flagged by Bandit: {bf['title']}."
            else:
                merged[key] = bf

        # 3. Merge Semgrep findings
        for sf in semgrep_findings:
            key = (sf["file"], sf["start_line"])
            if key in merged:
                existing = merged[key]
                existing["source_tool"] = f"{existing['source_tool']} + semgrep"
                if SEVERITY_ORDER.get(sf["severity"], 0) > SEVERITY_ORDER.get(existing["severity"], 0):
                    existing["severity"] = sf["severity"]
                existing["explanation"] += f" Also flagged by Semgrep: {sf['title']}."
            else:
                merged[key] = sf

        all_findings = list(merged.values())

        # Ensure all findings adhere strictly to Phase 7d requirements
        for f in all_findings:
            f["severity"] = normalize_severity(f["severity"])
            f["title"] = ensure_potential_label(f["title"])

        # Sort by severity descending, then file, then line
        all_findings.sort(
            key=lambda x: (
                -SEVERITY_ORDER.get(x["severity"], 0),
                x["file"],
                x["start_line"],
            )
        )

        return all_findings
