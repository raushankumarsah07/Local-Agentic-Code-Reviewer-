"""
Unit tests for Phase 9b: Retriever with Cosine Vector Search, Keyword Boost,
and Architectural Graph Expansion (callers, callees, importers).
"""

import json
import shutil
import tempfile
from pathlib import Path
import pytest

from app.config import Settings
from app.db.models import CodeEntity, GraphEdge, Project
from app.rag.chunker import CodeChunk
from app.rag.embedder import DeterministicEmbedder
from app.rag.retriever import (
    RepositoryRetriever,
    RetrievalResult,
    RetrievedChunk,
    apply_keyword_boost,
    extract_query_identifiers,
)
from app.rag.vector_store import ChromaStoreManager


@pytest.fixture
def temp_chroma_dir():
    temp_dir = Path(tempfile.mkdtemp(prefix="test_retriever_chroma_"))
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


# -----------------------------------------------------------------------------
# 1. Identifier Extraction and Keyword Boost Unit Tests
# -----------------------------------------------------------------------------

def test_extract_query_identifiers():
    """Verify code identifiers are extracted while stopwords and symbols are filtered."""
    query = "How does process_order invoke ValidateCart in checkout_service.py when handling payment?"
    idents = extract_query_identifiers(query)

    assert "process_order" in idents
    assert "ValidateCart" in idents
    assert "checkout_service" in idents
    assert "payment" in idents

    # Common English stopwords and query helper terms should be filtered out
    assert "how" not in [i.lower() for i in idents]
    assert "does" not in [i.lower() for i in idents]
    assert "when" not in [i.lower() for i in idents]
    assert "in" not in [i.lower() for i in idents]


def test_apply_keyword_boost_reorders_exact_identifier_match():
    """
    Verify exact symbol matches receive higher score boost and leapfrog
    candidates with higher initial raw cosine similarity.
    """
    candidates = [
        {
            "chunk_id": "chunk_generic",
            "content": "def generic_flow(data):\n    return data.run()",
            "similarity": 0.75,
            "metadata": {
                "file_path": "core/workflow.py",
                "symbol_name": "generic_flow",
                "entity_type": "function",
                "start_line": 10,
                "end_line": 20,
            },
        },
        {
            "chunk_id": "chunk_target",
            "content": "def calculate_tax(amount, rate):\n    return amount * rate",
            "similarity": 0.50,
            "metadata": {
                "file_path": "finance/tax.py",
                "symbol_name": "calculate_tax",
                "entity_type": "function",
                "start_line": 1,
                "end_line": 5,
            },
        },
    ]

    # Query specifically mentions the exact function 'calculate_tax'
    query_idents = ["calculate_tax"]
    boosted = apply_keyword_boost(
        candidates,
        query_identifiers=query_idents,
        symbol_match_boost=0.35,
    )

    assert len(boosted) == 2
    # chunk_target had lower similarity (0.50) but gets +0.35 (symbol match) + 0.10 (content word) = 0.95
    # chunk_generic stays at 0.75
    top_hit = boosted[0]
    assert top_hit.chunk_id == "chunk_target"
    assert top_hit.symbol_name == "calculate_tax"
    assert top_hit.boosted_score > boosted[1].boosted_score
    assert any("symbol:calculate_tax" in k for k in top_hit.matched_keywords)


def test_apply_keyword_boost_filepath_and_content_boost():
    """Verify file path matches and content word matches give proportional boosts."""
    candidates = [
        {
            "chunk_id": "c1",
            "content": "class AuthManager:\n    pass",
            "similarity": 0.60,
            "metadata": {
                "file_path": "services/auth_manager.py",
                "symbol_name": "AuthManager",
                "entity_type": "class",
                "start_line": 1,
                "end_line": 5,
            },
        }
    ]
    boosted = apply_keyword_boost(candidates, query_identifiers=["auth_manager"])
    assert len(boosted) == 1
    # Matches symbol (+0.35), file (+0.20), content (+0.10)
    assert boosted[0].boosted_score > 0.60
    assert any("file:auth_manager" in k for k in boosted[0].matched_keywords)


# -----------------------------------------------------------------------------
# 2. Graph Expansion Unit and Integration Tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_graph_expansion_adds_relevant_extra_context(test_db, temp_chroma_dir):
    """
    CRITICAL TEST FOR PHASE 9B:
    Shows that graph expansion retrieves callers, callees, and importers
    that provide essential architectural context beyond pure vector search.

    Architecture setup:
    - Target symbol: `process_order` (in `services/order.py`)
    - Callee: `validate_inventory` (in `services/inventory.py`) - called by `process_order`
    - Caller: `submit_checkout` (in `api/checkout.py`) - calls `process_order`
    - Importer: `controllers/web.py` imports `services/order.py`
    """
    project_id = "test_ecommerce_rag"

    # 1. Populate DB with Project, Code Entities, and Dependency Graph Edges
    project = Project(
        id=project_id,
        name="E-Commerce Store",
        path="/mock/path/ecommerce",
    )
    test_db.add(project)

    # Entity 1: Primary Target (process_order calls validate_inventory)
    ent_primary = CodeEntity(
        project_id=project_id,
        name="process_order",
        file_path="services/order.py",
        entity_type="function",
        start_line=10,
        end_line=25,
        details=json.dumps({
            "calls": ["validate_inventory"],
            "params": ["order_id", "user_id"],
            "docstring": "Core order processing pipeline.",
        }),
    )

    # Entity 2: Callee (validate_inventory in services/inventory.py)
    ent_callee = CodeEntity(
        project_id=project_id,
        name="validate_inventory",
        file_path="services/inventory.py",
        entity_type="function",
        start_line=5,
        end_line=15,
        details=json.dumps({"calls": [], "params": ["items"]}),
    )

    # Entity 3: Caller (submit_checkout in api/checkout.py invokes process_order)
    ent_caller = CodeEntity(
        project_id=project_id,
        name="submit_checkout",
        file_path="api/checkout.py",
        entity_type="function",
        start_line=40,
        end_line=60,
        details=json.dumps({"calls": ["services.order.process_order"]}),
    )

    # Entity 4: Importer module chunk in controllers/web.py
    ent_importer = CodeEntity(
        project_id=project_id,
        name="render_web_order",
        file_path="controllers/web.py",
        entity_type="function",
        start_line=1,
        end_line=20,
        details=json.dumps({"calls": []}),
    )

    # Graph edge: controllers/web.py imports services/order.py
    edge_importer = GraphEdge(
        project_id=project_id,
        source="controllers/web.py",
        target="services/order.py",
        edge_type="import",
        imported_symbols=json.dumps(["process_order"]),
    )

    # Entity 5: Unrelated code entity
    ent_unrelated = CodeEntity(
        project_id=project_id,
        name="format_date_string",
        file_path="utils/date_helpers.py",
        entity_type="function",
        start_line=1,
        end_line=10,
        details=json.dumps({"calls": []}),
    )

    test_db.add_all([ent_primary, ent_callee, ent_caller, ent_importer, ent_unrelated, edge_importer])
    test_db.commit()

    # 2. Index Code Chunks in ChromaDB
    embedder = DeterministicEmbedder(dimension=384)
    settings = Settings(CHROMA_PERSIST_DIR=temp_chroma_dir)
    store_manager = ChromaStoreManager(settings)

    chunks_to_index = [
        CodeChunk(
            chunk_id=f"{project_id}:order:process_order",
            content="def process_order(order_id, user_id):\n    # Process order pipeline\n    validate_inventory(order_id)\n    return {'status': 'processed'}",
            file_path="services/order.py",
            project_id=project_id,
            start_line=10,
            end_line=25,
            symbol_name="process_order",
            entity_type="function",
        ),
        CodeChunk(
            chunk_id=f"{project_id}:inv:validate_inventory",
            content="def validate_inventory(items):\n    # Check stock availability\n    return True",
            file_path="services/inventory.py",
            project_id=project_id,
            start_line=5,
            end_line=15,
            symbol_name="validate_inventory",
            entity_type="function",
        ),
        CodeChunk(
            chunk_id=f"{project_id}:api:submit_checkout",
            content="def submit_checkout(payload):\n    # Checkout entry point\n    return process_order(payload['id'], payload['user'])",
            file_path="api/checkout.py",
            project_id=project_id,
            start_line=40,
            end_line=60,
            symbol_name="submit_checkout",
            entity_type="function",
        ),
        CodeChunk(
            chunk_id=f"{project_id}:web:render_web_order",
            content="import services.order\ndef render_web_order():\n    return 'OK'",
            file_path="controllers/web.py",
            project_id=project_id,
            start_line=1,
            end_line=20,
            symbol_name="render_web_order",
            entity_type="function",
        ),
        CodeChunk(
            chunk_id=f"{project_id}:utils:date_helper",
            content="def format_date_string(dt):\n    return dt.isoformat()",
            file_path="utils/date_helpers.py",
            project_id=project_id,
            start_line=1,
            end_line=10,
            symbol_name="format_date_string",
            entity_type="function",
        ),
    ]

    await store_manager.index_chunks(
        project_id=project_id,
        chunks=chunks_to_index,
        embedder=embedder,
    )

    # 3. Instantiate Retriever
    retriever = RepositoryRetriever(
        settings=settings,
        embedder=embedder,
        store_manager=store_manager,
    )

    # Test query targeted directly at process_order with top_k=1
    query = "How does process_order work?"

    # A. Retrieval WITH graph expansion enabled
    result_with_graph = await retriever.retrieve(
        project_id=project_id,
        query=query,
        top_k=1,
        db=test_db,
        enable_graph_expansion=True,
        max_expansions=5,
    )

    # B. Retrieval WITHOUT graph expansion enabled
    result_without_graph = await retriever.retrieve(
        project_id=project_id,
        query=query,
        top_k=1,
        db=test_db,
        enable_graph_expansion=False,
    )

    # Assertions:
    # 1. Primary hit is process_order in both cases
    assert len(result_without_graph.primary_chunks) == 1
    assert result_without_graph.primary_chunks[0].symbol_name == "process_order"
    assert len(result_without_graph.expanded_chunks) == 0
    assert result_without_graph.total_chunks == 1

    # 2. Graph expansion successfully pulled in extra relevant architectural context
    assert len(result_with_graph.primary_chunks) == 1
    assert result_with_graph.primary_chunks[0].symbol_name == "process_order"

    assert len(result_with_graph.expanded_chunks) >= 2, (
        "Graph expansion should add callees, callers, and importers"
    )

    expansion_types = {c.expansion_type for c in result_with_graph.expanded_chunks}
    expanded_symbols = {c.symbol_name for c in result_with_graph.expanded_chunks}

    # Verify Callee was pulled in
    assert "callee" in expansion_types
    assert "validate_inventory" in expanded_symbols

    # Verify Caller was pulled in
    assert "caller" in expansion_types
    assert "submit_checkout" in expanded_symbols

    # Verify Importer was pulled in
    assert "importer" in expansion_types or any(c.file_path == "controllers/web.py" for c in result_with_graph.expanded_chunks)

    # Verify metadata on all expanded chunks
    for c in result_with_graph.expanded_chunks:
        assert c.is_expanded is True
        assert c.expansion_reason is not None
        assert len(c.expansion_reason) > 5

    # Verify summary explains the architectural neighbors
    summary = result_with_graph.graph_context_summary
    assert "process_order" in summary
    assert "Graph expansion added" in summary
    assert "Callee" in summary or "Caller" in summary

    # Unrelated function (format_date_string) should NEVER be expanded
    assert "format_date_string" not in expanded_symbols


@pytest.mark.asyncio
async def test_retriever_empty_query_returns_clean_result(temp_chroma_dir):
    """Verify empty or whitespace query returns clean empty result without errors."""
    settings = Settings(CHROMA_PERSIST_DIR=temp_chroma_dir)
    retriever = RepositoryRetriever(
        settings=settings,
        embedder=DeterministicEmbedder(),
        store_manager=ChromaStoreManager(settings),
    )

    result = await retriever.retrieve(project_id="test_p", query="   ", top_k=5)
    assert result.total_chunks == 0
    assert len(result.primary_chunks) == 0
    assert len(result.expanded_chunks) == 0
    assert "Empty query" in result.graph_context_summary
