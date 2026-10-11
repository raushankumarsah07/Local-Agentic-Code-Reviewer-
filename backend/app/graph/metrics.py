"""
Graph metrics and topology analysis module.
Calculates graph statistics, in-degree/out-degree centrality,
isolated files, density, and cycle presence using NetworkX.
"""

from typing import Any, Dict, List
import networkx as nx


def compute_graph_metrics(G: nx.DiGraph) -> Dict[str, Any]:
    """
    Computes graph topological metrics for software architecture evaluation.
    
    Args:
        G: Directed NetworkX graph of repository dependencies.
        
    Returns:
        Dictionary of computed topological and architectural metrics.
    """
    num_nodes = G.number_of_nodes()
    num_edges = G.number_of_edges()

    if num_nodes == 0:
        return {
            "node_count": 0,
            "edge_count": 0,
            "density": 0.0,
            "is_dag": True,
            "has_cycles": False,
            "isolated_nodes": [],
            "top_imported": [],
            "top_dependent": [],
        }

    # Density: ratio of actual edges to maximum possible directed edges
    density = round(nx.density(G), 4)

    # Check for circular dependency cycles (DAG check)
    is_dag = nx.is_directed_acyclic_graph(G)

    # Identify isolated nodes (neither imports nor is imported by anyone)
    isolated = [
        node for node in G.nodes()
        if G.in_degree(node) == 0 and G.out_degree(node) == 0
    ]

    # In-degree / Out-degree ranking for internal nodes
    internal_nodes = [
        node for node, data in G.nodes(data=True)
        if not data.get("is_external", False)
    ]

    in_degrees = dict(G.in_degree())
    out_degrees = dict(G.out_degree())

    top_imported = sorted(
        [{"file": node, "in_degree": in_degrees.get(node, 0)} for node in internal_nodes],
        key=lambda x: x["in_degree"],
        reverse=True,
    )[:5]

    top_dependent = sorted(
        [{"file": node, "out_degree": out_degrees.get(node, 0)} for node in internal_nodes],
        key=lambda x: x["out_degree"],
        reverse=True,
    )[:5]

    return {
        "node_count": num_nodes,
        "edge_count": num_edges,
        "density": density,
        "is_dag": is_dag,
        "has_cycles": not is_dag,
        "isolated_nodes": isolated,
        "top_imported": top_imported,
        "top_dependent": top_dependent,
    }
