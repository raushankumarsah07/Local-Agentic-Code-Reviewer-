"""
LangGraph StateGraph Workflow Definition.
Wraps all deterministic analysis and enrichment steps into a state graph
with typed shared state and conditional edges.
"""

from langgraph.graph import END, START, StateGraph

from app.agent.state import AnalysisState
from app.agent.steps import (
    build_graph_step,
    check_findings_enrichment_needed,
    enrich_findings_step,
    generate_docs_step,
    index_code_step,
    parse_step,
    review_findings_step,
    run_static_checks_step,
    scan_step,
)


def create_analysis_workflow():
    """
    Constructs and compiles the LangGraph StateGraph agent workflow.

    Workflow topology:
      START
        │
        ▼
      [scan] ───────────────── Discovers files, languages, sizes
        │
        ▼
      [parse] ──────────────── AST parser extracts entities (tolerant: logs & continues on errors)
        │
        ▼
      [build_graph] ────────── Builds NetworkX architecture graph & dependency edges
        │
        ▼
      [run_static_checks] ──── Complexity, dead code, cycles, god modules, security checks
        │
        ▼
      [index_code] ─────────── AST-aware chunking & ChromaDB vector store indexing
        │
        ▼
      <check_enrichment> ──── Conditional Edge:
        ├── "enrich_findings" ──► [enrich_findings] ── Extra call-graph & KB context for High/Critical
        │                                  │
        └── "review_findings"              │
                   │                       │
                   ▼                       ▼
            [review_findings] ◄────────────┘
                   │
                   ▼
            [generate_docs] ── Map-Reduce: per-file -> module -> repo overview -> Markdown
                   │
                   ▼
                  END
    """
    workflow = StateGraph(AnalysisState)

    # Register step nodes
    workflow.add_node("scan", scan_step)
    workflow.add_node("parse", parse_step)
    workflow.add_node("build_graph", build_graph_step)
    workflow.add_node("run_static_checks", run_static_checks_step)
    workflow.add_node("index_code", index_code_step)
    workflow.add_node("enrich_findings", enrich_findings_step)
    workflow.add_node("review_findings", review_findings_step)
    workflow.add_node("generate_docs", generate_docs_step)

    # Standard deterministic pipeline edges
    workflow.add_edge(START, "scan")
    workflow.add_edge("scan", "parse")
    workflow.add_edge("parse", "build_graph")
    workflow.add_edge("build_graph", "run_static_checks")
    workflow.add_edge("run_static_checks", "index_code")

    # Conditional branching: High/Critical findings get extra context before review
    workflow.add_conditional_edges(
        "index_code",
        check_findings_enrichment_needed,
        {
            "enrich_findings": "enrich_findings",
            "review_findings": "review_findings",
        },
    )

    # Convergence edges
    workflow.add_edge("enrich_findings", "review_findings")
    workflow.add_edge("review_findings", "generate_docs")
    workflow.add_edge("generate_docs", END)

    return workflow.compile()
