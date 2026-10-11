"""
Dead-Code Candidate Static Analyzer.
Combines NetworkX dependency graph reachability (BFS/DFS) from repository entry points
with Vulture dead-code AST scanning to identify candidate unused files, functions, and classes.

Explicitly documents and handles known false-positive cases:
- Decorators (e.g. @app.get, @pytest.fixture, @property, @dataclass)
- Dynamic attribute/module access (getattr, importlib, globals)
- __all__ public exports for library APIs
- Framework entry points and test harnesses
"""

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import networkx as nx

try:
    import vulture
    HAS_VULTURE = True
except ImportError:
    HAS_VULTURE = False

from app.graph.builder import DependencyGraphBuilder


# Standard conventional entry point file names
CONVENTIONAL_ENTRY_NAMES = {
    "main.py",
    "app.py",
    "cli.py",
    "manage.py",
    "server.py",
    "wsgi.py",
    "asgi.py",
    "index.py",
    "run.py",
    "setup.py",
    "__main__.py",
    "conftest.py",
}

# Known framework decorators that invoke functions implicitly
FRAMEWORK_DECORATORS = {
    "app.get", "app.post", "app.put", "app.delete", "app.patch", "app.route",
    "router.get", "router.post", "router.put", "router.delete", "router.patch",
    "fixture", "pytest.fixture", "task", "celery.task", "receiver",
    "property", "classmethod", "staticmethod", "dataclass", "abstractmethod",
}


def file_has_main_block(file_path: Path) -> bool:
    """Check if Python file contains 'if __name__ == \"__main__\":'."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                # Check for: __name__ == "__main__"
                comp = node.test
                if isinstance(comp, ast.Compare):
                    if (
                        isinstance(comp.left, ast.Name)
                        and comp.left.id == "__name__"
                        and len(comp.comparators) == 1
                        and isinstance(comp.comparators[0], ast.Constant)
                        and comp.comparators[0].value == "__main__"
                    ):
                        return True
    except Exception:
        pass
    return False


def extract_file_exported_names(file_path: Path) -> Set[str]:
    """Extract names defined in '__all__' list/tuple in the file."""
    exported: Set[str] = set()
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, (ast.List, ast.Tuple)):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    exported.add(elt.value)
    except Exception:
        pass
    return exported


def extract_function_decorators(file_path: Path) -> Dict[str, List[str]]:
    """Extract decorator names for each function/method in a file."""
    decorators_map: Dict[str, List[str]] = {}
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                dec_names: List[str] = []
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Name):
                        dec_names.append(dec.id)
                    elif isinstance(dec, ast.Attribute):
                        dec_names.append(f"{getattr(dec.value, 'id', '')}.{dec.attr}")
                    elif isinstance(dec, ast.Call):
                        func = dec.func
                        if isinstance(func, ast.Name):
                            dec_names.append(func.id)
                        elif isinstance(func, ast.Attribute):
                            dec_names.append(f"{getattr(func.value, 'id', '')}.{func.attr}")
                decorators_map[node.name] = dec_names
    except Exception:
        pass
    return decorators_map


class DeadCodeAnalyzer:
    """
    Identifies dead-code candidates via:
    1. Graph reachability (BFS/DFS) from entry points to detect unreachable files.
    2. Vulture static scanning to detect unused functions, classes, and methods.
    3. Cross-checking and false-positive annotation.
    """

    def __init__(self, entry_points: Optional[List[str]] = None):
        self.custom_entry_points = entry_points or []
        self.last_entry_points: List[str] = []

    def identify_entry_points(
        self,
        project_root: Path,
        graph: nx.DiGraph,
    ) -> List[str]:
        """
        Identify project entry points using conventions, AST checks, and in-degree zero modules.
        """
        entries: Set[str] = set(self.custom_entry_points)

        internal_nodes = [
            n for n, data in graph.nodes(data=True)
            if not data.get("is_external", False)
        ]

        for node_id in internal_nodes:
            file_path = project_root / node_id
            name = file_path.name.lower()

            # 1. Standard file name convention
            if name in CONVENTIONAL_ENTRY_NAMES:
                entries.add(node_id)
                continue

            # 2. Test files (e.g. test_*.py, *_test.py) are valid test entry points
            if name.startswith("test_") or name.endswith("_test.py"):
                entries.add(node_id)
                continue

            # 3. Check for if __name__ == "__main__":
            if file_path.exists() and file_has_main_block(file_path):
                entries.add(node_id)
                continue

            # 4. Root level __init__.py files (package roots)
            if node_id == "__init__.py" or node_id.endswith("/__init__.py") and node_id.count("/") <= 1:
                entries.add(node_id)

        # Fallback: If no explicit entry point is identified, take all internal nodes with in-degree = 0
        if not entries:
            for node_id in internal_nodes:
                if graph.in_degree(node_id) == 0:
                    entries.add(node_id)

        # Ultimate fallback: If still empty, treat all internal root-level nodes as entry roots
        if not entries:
            entries = set(internal_nodes)

        return sorted(list(entries))

    def compute_reachable_files(
        self,
        graph: nx.DiGraph,
        entry_points: List[str],
    ) -> Set[str]:
        """
        Perform BFS/DFS traversal from all entry points to find all reachable internal files.
        """
        reachable: Set[str] = set()
        for entry in entry_points:
            if graph.has_node(entry):
                reachable.add(entry)
                # NetworkX descendants gives all nodes reachable via directed edges
                descendants = nx.descendants(graph, entry)
                reachable.update(descendants)
        return reachable

    def run_vulture_scan(
        self,
        project_root: Path,
        file_paths: List[Path],
    ) -> List[Dict[str, Any]]:
        """
        Run Vulture static analyzer on project Python files.
        """
        if not HAS_VULTURE:
            return []

        v = vulture.Vulture(verbose=False)
        valid_paths = [str(p) for p in file_paths if p.exists() and p.suffix == ".py"]
        if not valid_paths:
            return []

        try:
            v.scavenge(valid_paths)
            unused_items = v.get_unused_code()
        except Exception:
            # Fallback to scanning file-by-file if whole-project scavenge fails
            unused_items = []
            for p in file_paths:
                try:
                    with open(p, "r", encoding="utf-8", errors="replace") as f:
                        v.scan(f.read(), filename=str(p))
                except Exception:
                    continue
            unused_items = v.get_unused_code()

        results: List[Dict[str, Any]] = []
        for item in unused_items:
            try:
                rel_file = Path(item.filename).relative_to(project_root).as_posix()
            except ValueError:
                rel_file = Path(item.filename).name

            results.append({
                "name": item.name,
                "typ": getattr(item, "typ", "symbol"),
                "first_lineno": getattr(item, "first_lineno", 1),
                "last_lineno": getattr(item, "last_lineno", getattr(item, "first_lineno", 1)),
                "confidence": getattr(item, "confidence", 60),
                "file": rel_file,
            })

        return results

    def analyze_project(
        self,
        project_root: Path,
        project_id: str,
        graph: Optional[nx.DiGraph] = None,
    ) -> List[Dict[str, Any]]:
        """
        Run full dead-code analysis:
        1. Construct NetworkX dependency graph if not provided.
        2. Identify entry points and compute reachability.
        3. Flag unreachable files as dead-code candidates.
        4. Run Vulture symbol scan.
        5. Filter known false-positive cases and document edge cases.
        """
        findings: List[Dict[str, Any]] = []
        if not project_root.exists() or not project_root.is_dir():
            return findings

        # Step 1: Ensure dependency graph exists
        if graph is None:
            builder = DependencyGraphBuilder(project_root=project_root, project_id=project_id)
            graph = builder.build()

        # Step 2: Identify entry points & compute graph reachability
        entry_points = self.identify_entry_points(project_root, graph)
        self.last_entry_points = entry_points
        reachable_nodes = self.compute_reachable_files(graph, entry_points)

        internal_nodes = {
            n for n, data in graph.nodes(data=True)
            if not data.get("is_external", False)
        }

        # Step 3: Flag completely unreachable files in the dependency graph
        unreachable_files = internal_nodes - reachable_nodes
        for unreach_file in sorted(list(unreachable_files)):
            file_path = project_root / unreach_file
            if not file_path.exists():
                continue

            findings.append({
                "project_id": project_id,
                "type": "dead_code",
                "severity": "Medium",
                "title": f"Dead-Code Candidate: Unreachable file '{unreach_file}'",
                "file": unreach_file,
                "start_line": 1,
                "end_line": max(1, graph.nodes[unreach_file].get("line_count", 1)),
                "evidence_snippet": f"# File '{unreach_file}' has no incoming import paths from detected entry points: {entry_points}",
                "source_tool": "graph_reachability",
                "explanation": (
                    f"File '{unreach_file}' is unreachable via graph reachability traversal (DFS/BFS) "
                    f"starting from detected repository entry points ({', '.join(entry_points)}). "
                    f"Note: Marked as a 'candidate' because this file could be invoked via dynamic imports, "
                    f"framework hooks, or external CLI commands. Verify before deleting."
                ),
            })

        # Step 4: Run Vulture AST scan on Python files
        py_files = [project_root / node_id for node_id in internal_nodes]
        vulture_items = self.run_vulture_scan(project_root, py_files)

        # Collect file decorator & __all__ maps for false positive filtering
        decorator_cache: Dict[str, Dict[str, List[str]]] = {}
        export_cache: Dict[str, Set[str]] = {}

        for item in vulture_items:
            rel_file = item["file"]
            file_path = project_root / rel_file
            symbol_name = item["name"]
            symbol_type = item["typ"]

            if rel_file not in decorator_cache:
                decorator_cache[rel_file] = extract_function_decorators(file_path)
            if rel_file not in export_cache:
                export_cache[rel_file] = extract_file_exported_names(file_path)

            file_decorators = decorator_cache[rel_file].get(symbol_name, [])
            file_exports = export_cache[rel_file]

            # False-Positive Check 1: Symbol exported in __all__
            is_exported_in_all = symbol_name in file_exports

            # False-Positive Check 2: Symbol uses framework decorator
            has_framework_decorator = any(
                dec in FRAMEWORK_DECORATORS or any(kw in dec.lower() for kw in ("get", "post", "route", "fixture", "task"))
                for dec in file_decorators
            )

            # False-Positive Check 3: Magic methods or test methods
            if symbol_name.startswith("__") and symbol_name.endswith("__"):
                continue
            if symbol_name.startswith("test_") or symbol_name.endswith("_test"):
                continue

            # Determine severity based on cross-check with graph reachability and confidence
            if rel_file in unreachable_files:
                severity = "High"
                source_tool = "graph_reachability+vulture"
            elif item["confidence"] >= 90:
                severity = "Medium"
                source_tool = "vulture"
            else:
                severity = "Low"
                source_tool = "vulture"

            # Construct false-positive advisory note
            advisory_notes: List[str] = []
            if is_exported_in_all:
                advisory_notes.append("Exported in '__all__' (intended for public library use)")
            if has_framework_decorator:
                advisory_notes.append(f"Uses decorator(s): {', '.join(file_decorators)} (likely invoked by framework)")
            if not advisory_notes:
                advisory_notes.append("Check for dynamic access (getattr, importlib, or plugin registries)")

            advisory_text = " | Potential false-positive reasons: " + "; ".join(advisory_notes)

            findings.append({
                "project_id": project_id,
                "type": "dead_code",
                "severity": severity,
                "title": f"Dead-Code Candidate: Unused {symbol_type} '{symbol_name}'",
                "file": rel_file,
                "start_line": item["first_lineno"],
                "end_line": item["last_lineno"],
                "evidence_snippet": f"def {symbol_name}(...):  # Vulture confidence: {item['confidence']}%",
                "source_tool": source_tool,
                "explanation": (
                    f"Vulture identified '{symbol_name}' ({symbol_type}) as unused with {item['confidence']}% confidence. "
                    f"Candidate evaluation required: {advisory_text}. "
                    f"Always verify dynamic lookups, framework routing, and decorators before removal."
                ),
            })

        return findings
