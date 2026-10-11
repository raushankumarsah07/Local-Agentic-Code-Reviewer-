"""
Dependency Graph Builder using NetworkX.
Constructs directed graphs where:
- Nodes represent source files (or external libraries).
- Edges represent import statements, resolving internal modules, packages, __init__.py,
  and relative imports, while cleanly isolating third-party/stdlib dependencies.
Computes in-degree and out-degree metrics and exports the graph as JSON.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

from app.parsing.base import ImportEntity, ParsedFile
from app.parsing.python_parser import PythonParser


class GraphNode(BaseModel):
    """Represents a node in the dependency graph."""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique node identifier (file relative path or external library)")
    label: str = Field(..., description="Display label for visualization")
    path: Optional[str] = Field(None, description="Filesystem relative path if internal file")
    is_external: bool = Field(False, description="True if this is an external third-party or stdlib library")
    language: str = Field("Python", description="Programming language or 'External'")
    in_degree: int = Field(0, description="Number of incoming edges (times imported by others)")
    out_degree: int = Field(0, description="Number of outgoing edges (modules imported by this file)")
    line_count: int = Field(0, description="Total lines in the file")
    file_size: int = Field(0, description="File size in bytes")


class GraphEdge(BaseModel):
    """Represents a directed dependency edge (source imports target)."""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique edge identifier, e.g. 'main.py->calculator.py'")
    source: str = Field(..., description="Source node ID (the importer)")
    target: str = Field(..., description="Target node ID (the imported entity)")
    edge_type: str = Field("import", description="Edge relationship type ('import', 'inheritance')")
    is_external: bool = Field(False, description="True if target is an external library")
    imported_symbols: List[str] = Field(default_factory=list, description="Symbols imported across this edge")
    line_number: Optional[int] = Field(None, description="Line number of first import statement")


class GraphData(BaseModel):
    """Complete JSON export payload of the software architecture graph."""
    model_config = ConfigDict(from_attributes=True)

    project_id: str
    total_nodes: int
    total_edges: int
    internal_nodes_count: int
    external_nodes_count: int
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    metrics: Dict[str, Any] = Field(default_factory=dict)


class DependencyGraphBuilder:
    """
    Builds and analyzes directed architecture graphs for software repositories.
    """

    def __init__(self, project_root: Path, project_id: str = "project"):
        self.project_root = project_root.resolve()
        self.project_id = project_id
        self.parser = PythonParser()

        # Pre-index all files in repository using normalized relative POSIX paths
        self.known_files: Set[str] = set()
        self.file_metadata: Dict[str, Dict[str, Any]] = {}

        self._index_workspace_files()

    def _index_workspace_files(self) -> None:
        """Scan directory and index all known file paths and basic metrics."""
        if not self.project_root.exists():
            return

        for p in self.project_root.rglob("*"):
            if p.is_file():
                rel_path = p.relative_to(self.project_root).as_posix()
                self.known_files.add(rel_path)
                try:
                    size = p.stat().st_size
                except OSError:
                    size = 0
                self.file_metadata[rel_path] = {
                    "size_bytes": size,
                    "line_count": 0,
                }

    def resolve_import(
        self,
        import_entity: ImportEntity,
        source_file_path: str,
    ) -> Tuple[str, bool]:
        """
        Resolve an import statement to either an internal repository file path
        or an external third-party/standard library name.
        
        Args:
            import_entity: The extracted ImportEntity from AST.
            source_file_path: The relative path of the file containing the import.
            
        Returns:
            Tuple of (resolved_identifier, is_external).
        """
        source_dir = Path(source_file_path).parent

        # ------------------------------------------------------------------
        # 1. Handle Relative Imports (level >= 1)
        # ------------------------------------------------------------------
        if import_entity.is_relative or import_entity.level > 0:
            # Move up (level - 1) directories from source_dir
            target_dir = source_dir
            for _ in range(import_entity.level - 1):
                target_dir = target_dir.parent

            mod_str = import_entity.module or ""
            mod_path_part = mod_str.replace(".", "/") if mod_str else ""

            candidates = []
            if mod_path_part:
                # e.g., from .helpers import validate -> source_dir / helpers.py
                candidates.append((target_dir / f"{mod_path_part}.py").as_posix())
                candidates.append((target_dir / mod_path_part / "__init__.py").as_posix())
                # Or imported symbol is actually a module file:
                candidates.append((target_dir / mod_path_part / f"{import_entity.imported_name}.py").as_posix())
            else:
                # e.g., from . import helpers
                candidates.append((target_dir / f"{import_entity.imported_name}.py").as_posix())
                candidates.append((target_dir / import_entity.imported_name / "__init__.py").as_posix())

            # Check normalized candidates against indexed known files
            for c in candidates:
                norm_c = os.path.normpath(c).replace("\\", "/")
                if norm_c in self.known_files:
                    return norm_c, False

            # If unresolvable relative import, return best normalized guess as internal
            fallback = os.path.normpath(candidates[0]).replace("\\", "/")
            return fallback, False

        # ------------------------------------------------------------------
        # 2. Handle Absolute Imports (level == 0)
        # ------------------------------------------------------------------
        mod_str = import_entity.module or import_entity.imported_name
        parts = mod_str.split(".")

        # Base directories inside project to search (root, or src/ directory)
        search_roots = ["", "src"]

        # Build candidate file patterns from most specific to least specific
        for root in search_roots:
            prefix = f"{root}/" if root else ""

            candidates = []
            # Candidate A: exact module as file (e.g. calculator.py or utils/helpers.py)
            candidates.append(f"{prefix}{'/'.join(parts)}.py")
            # Candidate B: exact module as package (e.g. utils/__init__.py)
            candidates.append(f"{prefix}{'/'.join(parts)}/__init__.py")
            # Candidate C: imported symbol is a file within module package
            # (e.g. from utils import helpers -> utils/helpers.py)
            if import_entity.module and import_entity.imported_name != "*":
                candidates.append(f"{prefix}{'/'.join(parts)}/{import_entity.imported_name}.py")
                candidates.append(f"{prefix}{'/'.join(parts)}/{import_entity.imported_name}/__init__.py")

            # Candidate D: progressively truncate parts to find containing module/package
            for i in range(len(parts) - 1, 0, -1):
                candidates.append(f"{prefix}{'/'.join(parts[:i])}.py")
                candidates.append(f"{prefix}{'/'.join(parts[:i])}/__init__.py")

            for c in candidates:
                norm_c = os.path.normpath(c).replace("\\", "/")
                if norm_c in self.known_files:
                    return norm_c, False

        # ------------------------------------------------------------------
        # 3. Not Found in Workspace -> Marked as External Library
        # ------------------------------------------------------------------
        top_level_package = parts[0]
        return top_level_package, True

    def build_graph(
        self,
        include_external: bool = True,
        parsed_files: Optional[Dict[str, ParsedFile]] = None,
    ) -> nx.DiGraph:
        """
        Construct a NetworkX directed graph (DiGraph) representing the project architecture.
        
        Args:
            include_external: If True, external libraries are added as target nodes.
            parsed_files: Optional pre-parsed files dictionary; parses on-the-fly if omitted.
            
        Returns:
            networkx.DiGraph instance.
        """
        G = nx.DiGraph()

        # Collect and parse all Python files
        py_files = [f for f in self.known_files if f.endswith(".py")]

        parsed_map: Dict[str, ParsedFile] = {}
        for rel_file in py_files:
            if parsed_files and rel_file in parsed_files:
                parsed_map[rel_file] = parsed_files[rel_file]
            else:
                full_path = self.project_root / rel_file
                parsed_map[rel_file] = self.parser.parse_file(full_path, project_root=self.project_root)

        # 1. Add all internal Python files as nodes
        for rel_file, parsed in parsed_map.items():
            line_count = 0
            full_path = self.project_root / rel_file
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    line_count = len(f.read().splitlines())
            except Exception:
                pass

            G.add_node(
                rel_file,
                id=rel_file,
                label=Path(rel_file).name,
                path=rel_file,
                is_external=False,
                language="Python",
                line_count=line_count,
                file_size=self.file_metadata.get(rel_file, {}).get("size_bytes", 0),
            )

        # 2. Add edges from imports (merging multiple imports between same source and target)
        # Key: (source, target) -> { "is_external": bool, "symbols": Set[str], "line": int }
        edge_map: Dict[Tuple[str, str], Dict[str, Any]] = {}

        for source_file, parsed in parsed_map.items():
            if not parsed.is_parsable:
                continue

            for imp in parsed.imports:
                target, is_external = self.resolve_import(imp, source_file)

                # Skip self-imports if any
                if target == source_file:
                    continue

                if is_external and not include_external:
                    continue

                # Add external node if needed
                if is_external and target not in G:
                    G.add_node(
                        target,
                        id=target,
                        label=f"{target} (external)",
                        path=None,
                        is_external=True,
                        language="External",
                        line_count=0,
                        file_size=0,
                    )

                key = (source_file, target)
                if key not in edge_map:
                    edge_map[key] = {
                        "is_external": is_external,
                        "symbols": set(),
                        "line": imp.line_number,
                    }
                edge_map[key]["symbols"].add(imp.imported_name)

        # 3. Add consolidated edges to NetworkX DiGraph
        for (src, dst), data in edge_map.items():
            edge_id = f"{src}->{dst}"
            G.add_edge(
                src,
                dst,
                id=edge_id,
                source=src,
                target=dst,
                edge_type="import",
                is_external=data["is_external"],
                imported_symbols=sorted(list(data["symbols"])),
                line_number=data["line"],
            )

        return G

    def export_json(
        self,
        G: Optional[nx.DiGraph] = None,
        include_external: bool = True,
    ) -> GraphData:
        """
        Export the graph to structured GraphData with node degrees and metrics.
        """
        if G is None:
            G = self.build_graph(include_external=include_external)

        from app.graph.metrics import compute_graph_metrics

        nodes_list: List[GraphNode] = []
        internal_count = 0
        external_count = 0

        # Calculate in-degree and out-degree using NetworkX
        in_degrees = dict(G.in_degree())
        out_degrees = dict(G.out_degree())

        for node_id, attrs in G.nodes(data=True):
            is_ext = attrs.get("is_external", False)
            if is_ext:
                external_count += 1
            else:
                internal_count += 1

            node = GraphNode(
                id=node_id,
                label=attrs.get("label", node_id),
                path=attrs.get("path"),
                is_external=is_ext,
                language=attrs.get("language", "Python"),
                in_degree=in_degrees.get(node_id, 0),
                out_degree=out_degrees.get(node_id, 0),
                line_count=attrs.get("line_count", 0),
                file_size=attrs.get("file_size", 0),
            )
            nodes_list.append(node)

        edges_list: List[GraphEdge] = []
        for src, dst, attrs in G.edges(data=True):
            edge = GraphEdge(
                id=attrs.get("id", f"{src}->{dst}"),
                source=src,
                target=dst,
                edge_type=attrs.get("edge_type", "import"),
                is_external=attrs.get("is_external", False),
                imported_symbols=attrs.get("imported_symbols", []),
                line_number=attrs.get("line_number"),
            )
            edges_list.append(edge)

        # Sort nodes and edges for deterministic, consistent ordering
        nodes_list.sort(key=lambda n: (n.is_external, n.id))
        edges_list.sort(key=lambda e: (e.source, e.target))

        metrics = compute_graph_metrics(G)

        return GraphData(
            project_id=self.project_id,
            total_nodes=len(nodes_list),
            total_edges=len(edges_list),
            internal_nodes_count=internal_count,
            external_nodes_count=external_count,
            nodes=nodes_list,
            edges=edges_list,
            metrics=metrics,
        )
