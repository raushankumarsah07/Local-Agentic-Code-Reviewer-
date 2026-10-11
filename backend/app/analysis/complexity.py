"""
Complexity and Long-Function Static Analyzer.
Computes McCabe cyclomatic complexity and detects overly long functions with configurable thresholds.
"""

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from radon.complexity import cc_visit
    HAS_RADON = True
except ImportError:
    HAS_RADON = False


@dataclass
class ComplexityThresholds:
    """Configurable thresholds for cyclomatic complexity and function length."""
    complexity_warning_threshold: int = 10
    complexity_critical_threshold: int = 15
    long_function_warning_lines: int = 50
    long_function_critical_lines: int = 100


class ASTCyclomaticComplexityVisitor(ast.NodeVisitor):
    """
    Fallback Pure-Python AST Visitor to calculate McCabe Cyclomatic Complexity.
    McCabe formula: M = Decision Points + 1
    Decision points include If, For, While, ExceptHandler, Assert, With, and BoolOp (and/or).
    """

    def __init__(self):
        self.functions: List[Dict[str, Any]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._analyze_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._analyze_function(node)

    def _analyze_function(self, node: ast.AST):
        name = getattr(node, "name", "anonymous")
        start_line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", start_line)

        # Base complexity for any function is 1
        complexity = 1

        for child in ast.walk(node):
            # Don't count decision points of nested functions for this function
            if child is not node and isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            if isinstance(child, (ast.If, ast.IfExp)):
                complexity += 1
            elif isinstance(child, (ast.For, ast.AsyncFor, ast.While)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, ast.Assert):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                # Each 'and' or 'or' adds a branch: len(values) - 1
                complexity += max(0, len(child.values) - 1)
            elif isinstance(child, getattr(ast, "Match", ())):
                complexity += 1
            elif isinstance(child, getattr(ast, "match_case", ())):
                if getattr(child, "guard", None) is not None:
                    complexity += 1

        self.functions.append({
            "name": name,
            "complexity": complexity,
            "start_line": start_line,
            "end_line": end_line,
        })

        # Continue traversing children (for nested functions)
        self.generic_visit(node)


class ComplexityAnalyzer:
    """
    Analyzes Python source files for high cyclomatic complexity and long functions.
    Produces findings conforming to the Finding database model.
    """

    def __init__(self, thresholds: Optional[ComplexityThresholds] = None):
        self.thresholds = thresholds or ComplexityThresholds()

    def analyze_code(
        self,
        code: str,
        file_path: str,
        project_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Analyze code string and return list of findings.
        """
        findings: List[Dict[str, Any]] = []
        if not code or not code.strip():
            return findings

        code_lines = code.splitlines()

        # Step 1: Extract functions and cyclomatic complexity
        func_metrics = self._extract_function_metrics(code)

        for fn in func_metrics:
            fn_name = fn["name"]
            complexity = fn["complexity"]
            start_line = fn["start_line"]
            end_line = fn["end_line"]
            line_count = max(1, end_line - start_line + 1)

            # Generate evidence snippet (up to 5 lines of definition)
            snippet_end = min(len(code_lines), start_line + 4)
            snippet = "\n".join(code_lines[start_line - 1 : snippet_end]) if code_lines else ""

            # Check Cyclomatic Complexity threshold
            if complexity >= self.thresholds.complexity_warning_threshold:
                if complexity >= self.thresholds.complexity_critical_threshold:
                    severity = "High" if complexity < 25 else "Critical"
                else:
                    severity = "Medium"

                findings.append({
                    "project_id": project_id,
                    "type": "complexity",
                    "severity": severity,
                    "title": f"High Cyclomatic Complexity ({complexity}) in function '{fn_name}'",
                    "file": file_path,
                    "start_line": start_line,
                    "end_line": end_line,
                    "evidence_snippet": snippet,
                    "source_tool": "mccabe",
                    "explanation": (
                        f"Function '{fn_name}' has a McCabe cyclomatic complexity of {complexity} "
                        f"(threshold is {self.thresholds.complexity_warning_threshold}). "
                        f"High complexity indicates multiple nested branches, loops, or conditionals, "
                        f"making the code harder to test, maintain, and reason about. "
                        f"Recommendation: Refactor and decompose into smaller, single-purpose helper functions."
                    ),
                })

            # Check Long-Function threshold
            if line_count >= self.thresholds.long_function_warning_lines:
                severity = (
                    "High"
                    if line_count >= self.thresholds.long_function_critical_lines
                    else "Medium"
                )
                findings.append({
                    "project_id": project_id,
                    "type": "complexity",
                    "severity": severity,
                    "title": f"Long Function '{fn_name}' ({line_count} lines)",
                    "file": file_path,
                    "start_line": start_line,
                    "end_line": end_line,
                    "evidence_snippet": snippet,
                    "source_tool": "complexity_analyzer",
                    "explanation": (
                        f"Function '{fn_name}' spans {line_count} lines "
                        f"(warning threshold is {self.thresholds.long_function_warning_lines} lines). "
                        f"Long functions frequently violate the Single Responsibility Principle, "
                        f"increase cognitive load, and hide subtle bugs. "
                        f"Recommendation: Break this function into modular steps."
                    ),
                })

        return findings

    def _extract_function_metrics(self, code: str) -> List[Dict[str, Any]]:
        """
        Extract function metrics using Radon if available, falling back to AST visitor.
        """
        metrics: List[Dict[str, Any]] = []

        if HAS_RADON:
            try:
                radon_results = cc_visit(code)
                for item in radon_results:
                    # Filter for functions and methods (classes have 'classname', functions have 'name')
                    # cc_visit returns Function, Method, and Class objects
                    is_func = hasattr(item, "is_method") or item.__class__.__name__ in ("Function", "Method")
                    if is_func:
                        metrics.append({
                            "name": item.name,
                            "complexity": item.complexity,
                            "start_line": item.lineno,
                            "end_line": item.endline,
                        })
                if metrics:
                    return metrics
            except Exception:
                # Fall back to pure AST if radon parse fails
                pass

        # Fallback to AST visitor
        try:
            tree = ast.parse(code)
            visitor = ASTCyclomaticComplexityVisitor()
            visitor.visit(tree)
            return visitor.functions
        except SyntaxError:
            return []

    def analyze_file(
        self,
        file_path: Path,
        project_root: Path,
        project_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Analyze a single file on disk.
        """
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

    def analyze_project(
        self,
        project_root: Path,
        project_id: str,
        file_extensions: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Walk project workspace and analyze all Python files for complexity issues.
        """
        if file_extensions is None:
            file_extensions = [".py"]

        all_findings: List[Dict[str, Any]] = []
        if not project_root.exists() or not project_root.is_dir():
            return all_findings

        # Traverse repository avoiding hidden/cache folders
        ignore_dirs = {
            "node_modules", ".git", ".venv", "venv", "__pycache__",
            ".pytest_cache", "build", "dist", ".idea", ".vscode"
        }

        for path in project_root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in ignore_dirs or part.startswith(".") for part in path.parts):
                continue
            if path.suffix.lower() in file_extensions:
                file_findings = self.analyze_file(path, project_root, project_id)
                all_findings.extend(file_findings)

        return all_findings
