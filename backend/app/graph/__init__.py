"""
Graph package for software architecture and dependency graph generation.
Built on NetworkX to model files as nodes and imports/calls/inheritance as directed edges.
"""

from app.graph.builder import DependencyGraphBuilder, GraphNode, GraphEdge, GraphData
from app.graph.metrics import compute_graph_metrics

__all__ = [
    "DependencyGraphBuilder",
    "GraphNode",
    "GraphEdge",
    "GraphData",
    "compute_graph_metrics",
]
