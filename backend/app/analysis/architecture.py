"""
Architecture Static Analyzer: Circular Dependencies & God-Module Coupling.
- Detects circular dependency cycles using Tarjan's Strongly Connected Components (SCC) algorithm.
- Computes degree, degree centrality, betweenness centrality, and instability to flag tightly coupled "God Modules".
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import networkx as nx

from app.graph.builder import DependencyGraphBuilder


class ArchitectureAnalyzer:
    """
    Analyzes project dependency graphs for architectural anti-patterns:
    1. Circular dependencies (Tarjan's strongly connected components / elementary cycles).
    2. God modules (excessive degree and betweenness centrality).
    """

    def __init__(
        self,
        total_degree_threshold: int = 8,
        betweenness_threshold: float = 0.20,
    ):
        self.total_degree_threshold = total_degree_threshold
        self.betweenness_threshold = betweenness_threshold

    def detect_circular_dependencies(
        self,
        graph: nx.DiGraph,
        project_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Identify circular dependency cycles using Tarjan's strongly connected components (SCC).
        Isolates internal subgraphs and extracts simple elementary cycles within each SCC.
        """
        findings: List[Dict[str, Any]] = []

        # Only analyze internal repository files (ignore external stdlib/pip packages)
        internal_nodes = [
            n for n, data in graph.nodes(data=True)
            if not data.get("is_external", False)
        ]
        if not internal_nodes:
            return findings

        internal_subgraph = graph.subgraph(internal_nodes).copy()

        # Step 1: Tarjan's Strongly Connected Components algorithm
        # A component with > 1 node (or a self loop) indicates a cycle
        scc_components = list(nx.strongly_connected_components(internal_subgraph))

        cycle_sets_seen: Set[Tuple[str, ...]] = set()

        for scc in scc_components:
            # An SCC with >= 2 nodes contains at least one cycle
            if len(scc) >= 2 or (len(scc) == 1 and internal_subgraph.has_edge(list(scc)[0], list(scc)[0])):
                scc_subgraph = internal_subgraph.subgraph(scc)
                
                # Extract elementary directed cycles in this SCC
                try:
                    elementary_cycles = list(nx.simple_cycles(scc_subgraph))
                except Exception:
                    elementary_cycles = [sorted(list(scc))]

                for cycle in elementary_cycles:
                    # Normalize cycle ordering to avoid duplicate permutations
                    min_idx = cycle.index(min(cycle))
                    canonical_cycle = tuple(cycle[min_idx:] + cycle[:min_idx])
                    if canonical_cycle in cycle_sets_seen:
                        continue
                    cycle_sets_seen.add(canonical_cycle)

                    # Cycle representation: A -> B -> C -> A
                    cycle_chain = list(canonical_cycle) + [canonical_cycle[0]]
                    cycle_path_str = " -> ".join(cycle_chain)

                    primary_file = canonical_cycle[0]
                    cycle_len = len(canonical_cycle)

                    # Format formatted evidence snippet
                    lines = [f"# Circular Import Chain ({cycle_len} modules):"]
                    for i in range(len(canonical_cycle)):
                        curr_f = canonical_cycle[i]
                        next_f = canonical_cycle[(i + 1) % cycle_len]
                        edge_data = internal_subgraph.get_edge_data(curr_f, next_f, default={})
                        symbols = edge_data.get("imported_symbols", [])
                        sym_info = f" (imports: {', '.join(symbols)})" if symbols else ""
                        lines.append(f"  {curr_f} ──> {next_f}{sym_info}")
                    evidence = "\n".join(lines)

                    # 2-node mutual import is Critical (immediate deadlock); larger cycles are High
                    severity = "Critical" if cycle_len == 2 else "High"

                    findings.append({
                        "project_id": project_id,
                        "type": "cycle",
                        "severity": severity,
                        "title": f"Circular Dependency Cycle ({cycle_len} files): {cycle_path_str}",
                        "file": primary_file,
                        "start_line": 1,
                        "end_line": max(1, graph.nodes[primary_file].get("line_count", 1)),
                        "evidence_snippet": evidence,
                        "source_tool": "tarjan_scc",
                        "explanation": (
                            f"Tarjan's algorithm detected an import cycle involving {cycle_len} files: {cycle_path_str}. "
                            f"In Python, circular imports frequently cause runtime 'ImportError: cannot import name ... from partially initialized module' "
                            f"because a module is imported before its own definitions have executed. "
                            f"Recommendation: 1) Extract shared types/models into a dedicated leaf module; "
                            f"2) Apply Dependency Inversion (use callbacks or interfaces); or "
                            f"3) Move the import statement inside the specific function (lazy import)."
                        ),
                    })

        return findings

    def detect_god_modules(
        self,
        graph: nx.DiGraph,
        project_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Identify tightly coupled 'God Modules' using:
        - In-degree (fan-in / afferent coupling)
        - Out-degree (fan-out / efferent coupling)
        - Total degree and degree centrality
        - Betweenness centrality (bottleneck / bridge importance)
        """
        findings: List[Dict[str, Any]] = []

        internal_nodes = [
            n for n, data in graph.nodes(data=True)
            if not data.get("is_external", False)
        ]
        n_count = len(internal_nodes)
        if n_count < 3:
            return findings

        internal_subgraph = graph.subgraph(internal_nodes).copy()

        # Compute degree metrics
        in_degrees = dict(internal_subgraph.in_degree())
        out_degrees = dict(internal_subgraph.out_degree())

        # Compute centrality metrics
        try:
            betweenness = nx.betweenness_centrality(internal_subgraph, normalized=True)
        except Exception:
            betweenness = {n: 0.0 for n in internal_nodes}

        try:
            deg_centrality = nx.degree_centrality(internal_subgraph)
        except Exception:
            deg_centrality = {n: 0.0 for n in internal_nodes}

        # Dynamic threshold adjustment for smaller or larger repositories
        effective_degree_threshold = max(
            4,
            min(self.total_degree_threshold, int(n_count * 0.35))
        )

        for node in internal_nodes:
            in_deg = in_degrees.get(node, 0)
            out_deg = out_degrees.get(node, 0)
            total_deg = in_deg + out_deg
            b_cent = betweenness.get(node, 0.0)
            d_cent = deg_centrality.get(node, 0.0)

            # Instability metric (Martin's metric): Ce / (Ca + Ce)
            instability = round(out_deg / total_deg, 2) if total_deg > 0 else 0.0

            is_high_degree = total_deg >= effective_degree_threshold
            is_high_betweenness = b_cent >= self.betweenness_threshold and n_count >= 5

            if is_high_degree or is_high_betweenness:
                # Severity determination
                if is_high_degree and is_high_betweenness:
                    severity = "High"
                else:
                    severity = "Medium"

                # Snippet showing coupling statistics
                evidence = (
                    f"# Coupling Metrics for '{node}':\n"
                    f"  In-Degree (Afferent / incoming imports): {in_deg}\n"
                    f"  Out-Degree (Efferent / outgoing imports): {out_deg}\n"
                    f"  Total Degree: {total_deg} (Threshold: {effective_degree_threshold})\n"
                    f"  Degree Centrality: {d_cent:.2f}\n"
                    f"  Betweenness Centrality: {b_cent:.2f} (Threshold: {self.betweenness_threshold})\n"
                    f"  Instability Index: {instability}"
                )

                findings.append({
                    "project_id": project_id,
                    "type": "coupling",
                    "severity": severity,
                    "title": f"High Coupling / God Module: '{node}' (Degree: {total_deg}, Centrality: {b_cent:.2f})",
                    "file": node,
                    "start_line": 1,
                    "end_line": max(1, graph.nodes[node].get("line_count", 1)),
                    "evidence_snippet": evidence,
                    "source_tool": "coupling_analyzer",
                    "explanation": (
                        f"Module '{node}' exhibits high topological coupling with {total_deg} connections "
                        f"({in_deg} files depend on it, and it imports {out_deg} files) with betweenness centrality of {b_cent:.2f}. "
                        f"God modules centralize too much responsibility and act as system chokepoints. "
                        f"Any modification to this file creates a large ripple effect across the codebase and impedes isolated unit testing. "
                        f"Recommendation: Decompose into cohesive, single-responsibility submodules following the Interface Segregation Principle."
                    ),
                })

        return findings

    def analyze_project(
        self,
        project_root: Path,
        project_id: str,
        graph: Optional[nx.DiGraph] = None,
    ) -> List[Dict[str, Any]]:
        """
        Run complete architecture analysis for circular dependencies and god modules.
        """
        if graph is None:
            builder = DependencyGraphBuilder(project_root=project_root, project_id=project_id)
            graph = builder.build()

        cycle_findings = self.detect_circular_dependencies(graph=graph, project_id=project_id)
        god_findings = self.detect_god_modules(graph=graph, project_id=project_id)

        return cycle_findings + god_findings
