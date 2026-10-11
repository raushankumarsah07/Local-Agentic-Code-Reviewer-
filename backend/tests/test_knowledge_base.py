"""
Unit and integration tests for Phase 9c:
Knowledge Base Documentation, Markdown Chunking, ChromaDB Indexing,
and Grounded Retrieval for Security Finding Explanations.
"""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock
import pytest

from app.config import Settings
from app.db.models import Finding, Project
from app.llm.client import LLMClient, LLMResponse
from app.llm.explainer import FindingExplainerService
from app.rag.embedder import DeterministicEmbedder
from app.rag.knowledge_base import (
    KnowledgeBaseManager,
    chunk_markdown_file,
    resolve_knowledge_base_dir,
)
from app.rag.vector_store import ChromaStoreManager


@pytest.fixture
def temp_chroma_dir():
    temp_dir = Path(tempfile.mkdtemp(prefix="test_kb_chroma_"))
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


# -----------------------------------------------------------------------------
# 1. Verification of the 7 Required Knowledge Base Files
# -----------------------------------------------------------------------------

def test_all_seven_knowledge_base_files_exist():
    """Verify that all 7 required topic documentation files exist in docs/knowledge/."""
    kb_dir = resolve_knowledge_base_dir()
    assert kb_dir.exists() and kb_dir.is_dir(), f"Knowledge dir not found: {kb_dir}"

    expected_files = [
        "hardcoded_secrets.md",
        "sql_injection.md",
        "command_injection.md",
        "insecure_deserialization.md",
        "authentication_basics.md",
        "python_best_practices.md",
        "complexity_guidance.md",
    ]

    for fname in expected_files:
        fpath = kb_dir / fname
        assert fpath.exists(), f"Missing required knowledge file: {fname}"
        content = fpath.read_text(encoding="utf-8")
        assert len(content) > 200, f"Knowledge file {fname} is unexpectedly short or empty."
        assert "# " in content, f"Knowledge file {fname} lacks H1 markdown header."


# -----------------------------------------------------------------------------
# 2. Markdown Chunking
# -----------------------------------------------------------------------------

def test_chunk_markdown_file_extracts_structured_sections():
    """Verify markdown parser preserves document title and section headings in chunk content."""
    kb_dir = resolve_knowledge_base_dir()
    sql_file = kb_dir / "sql_injection.md"

    chunks = chunk_markdown_file(sql_file)
    assert len(chunks) >= 3

    topics = {c.topic for c in chunks}
    assert topics == {"sql_injection"}

    doc_titles = {c.doc_title for c in chunks}
    assert any("SQL Injection" in t for t in doc_titles)

    # Verify that chunk content includes contextual hierarchical headers for embedding
    remediation_chunk = next((c for c in chunks if "Secure Remediation" in c.section_title or "Parameterized" in c.content), None)
    assert remediation_chunk is not None
    assert "SQL Injection" in remediation_chunk.content
    assert remediation_chunk.char_count > 50


# -----------------------------------------------------------------------------
# 3. ChromaDB Indexing and Topical Retrieval
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_index_and_query_knowledge_base(temp_chroma_dir):
    """
    Verify indexing all 7 files into the separate 'knowledge_base' ChromaDB collection
    and querying for grounded advice on security topics.
    """
    settings = Settings(
        CHROMA_PERSIST_DIR=temp_chroma_dir,
        KNOWLEDGE_BASE_COLLECTION="knowledge_base",
    )
    embedder = DeterministicEmbedder(dimension=384)
    store = ChromaStoreManager(settings)

    kb_manager = KnowledgeBaseManager(
        settings=settings,
        embedder=embedder,
        store_manager=store,
    )

    # 1. Index knowledge base
    count = await kb_manager.index_knowledge_base(force=True)
    assert count >= 15, "Expected at least 15 chunks across 7 knowledge documents"

    # Verify collection isolation
    kb_coll = kb_manager.get_collection()
    assert kb_coll.count() == count
    assert kb_coll.name == "knowledge_base"

    # Idempotency check: force=False should not duplicate
    count_idempotent = await kb_manager.index_knowledge_base(force=False)
    assert count_idempotent == count
    assert kb_coll.count() == count

    # 2. Query for SQL injection advice
    sql_chunks = await kb_manager.query_knowledge_base(
        query="Prevent SQL injection using parameterized queries with cursor.execute",
        top_k=2,
        topic_filter="sql_injection",
    )
    assert len(sql_chunks) > 0
    assert sql_chunks[0].topic == "sql_injection"
    assert "SQL" in sql_chunks[0].doc_title
    assert sql_chunks[0].similarity > 0.0

    # 3. Query for hardcoded secrets
    secret_chunks = await kb_manager.query_knowledge_base(
        query="How to avoid committing API keys and secret passwords to git",
        top_k=2,
    )
    assert len(secret_chunks) > 0
    assert any(c.topic == "hardcoded_secrets" for c in secret_chunks)

    # 4. Query for complexity guidance
    complexity_chunks = await kb_manager.query_knowledge_base(
        query="High cyclomatic complexity McCabe score and guard clauses",
        top_k=2,
    )
    assert len(complexity_chunks) > 0
    assert any(c.topic == "complexity_guidance" for c in complexity_chunks)


# -----------------------------------------------------------------------------
# 4. Use in Explaining Security Findings
# -----------------------------------------------------------------------------

class MockLLMClient(LLMClient):
    """Mock LLM client capturing prompts to verify RAG context injection."""

    def __init__(self):
        self.model_name = "mock-model"
        self.last_messages = []

    async def chat(self, messages, response_schema=None, schema=None, temperature=0.1):
        self.last_messages = list(messages)
        valid_json = json.dumps({
            "problem": "Unsanitized user input formatted directly into SQL statement.",
            "risk": "Critical: Attackers can execute arbitrary SQL injection payloads to extract data.",
            "recommended_fix": "Use parameterized queries with cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,)).",
            "confidence_note": "High confidence based on AST detection.",
        })
        return LLMResponse(
            content=valid_json,
            model_name="mock-model",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            latency_ms=45,
            tokens_per_second=30.0,
        )

    async def health_check(self):
        return {"status": "healthy"}



@pytest.mark.asyncio
async def test_explainer_injects_knowledge_base_guidance(test_db, temp_chroma_dir):
    """
    CRITICAL PHASE 9C TEST:
    Verify that when explaining a security finding, the Knowledge Base is queried
    and authoritative guidance (e.g., OWASP/remediation patterns) is injected
    into the prompt provided to the local LLM.
    """
    settings = Settings(
        CHROMA_PERSIST_DIR=temp_chroma_dir,
        KNOWLEDGE_BASE_COLLECTION="knowledge_base",
    )
    embedder = DeterministicEmbedder(dimension=384)
    store = ChromaStoreManager(settings)
    kb_manager = KnowledgeBaseManager(settings=settings, embedder=embedder, store_manager=store)

    # Pre-index knowledge base
    await kb_manager.index_knowledge_base(force=True)

    # 1. Setup Project and Security Finding in test DB
    project = Project(id="proj_kb_test", name="Security Test Project", path="/mock/sec")
    test_db.add(project)

    finding = Finding(
        project_id="proj_kb_test",
        title="SQL built by string concatenation",
        type="security",
        severity="High",
        file="app/routes/users.py",
        start_line=24,
        end_line=25,
        source_tool="ast_rules",
        evidence_snippet="query = f'SELECT * FROM users WHERE id = {user_id}'\ncursor.execute(query)",
    )
    test_db.add(finding)
    test_db.commit()

    # 2. Instantiate explainer service with mock client and configured kb_manager
    mock_client = MockLLMClient()
    explainer = FindingExplainerService(
        client=mock_client,
        settings=settings,
        kb_manager=kb_manager,
    )

    # 3. Explain the finding
    res = await explainer.explain_finding(finding.id, test_db, force=True)

    assert res.status == "success"
    assert res.explanation.problem is not None

    # 4. Verify that the LLM user prompt received the authoritative Knowledge Base guidance
    assert len(mock_client.last_messages) == 2
    user_message = mock_client.last_messages[1]["content"]

    assert "RELEVANT KNOWLEDGE BASE & ARCHITECTURAL GUIDANCE (RAG):" in user_message
    assert "KNOWLEDGE BASE GUIDANCE" in user_message
    assert "SQL Injection" in user_message or "sql_injection" in user_message
    assert "Parameterized" in user_message or "cursor.execute" in user_message
