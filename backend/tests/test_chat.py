"""
Unit and integration tests for Phase 9d:
Repository Chat Engine, Prompt Builder with Token Budgeting,
Mandatory Source Citations [file:line-range], Honest Unanswerable Detection,
and FastAPI Chat Endpoint.
"""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db.models import Project
from app.llm.client import LLMClient, LLMResponse
from app.rag.chat import (
    ChatMessage,
    CitationItem,
    RepositoryChatEngine,
    build_chat_prompt,
    extract_citations_from_text,
)
from app.rag.chunker import CodeChunk
from app.rag.embedder import DeterministicEmbedder
from app.rag.retriever import RepositoryRetriever, RetrievedChunk
from app.rag.vector_store import ChromaStoreManager


@pytest.fixture
def temp_chroma_dir():
    temp_dir = Path(tempfile.mkdtemp(prefix="test_chat_chroma_"))
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


# -----------------------------------------------------------------------------
# 1. Citation Parsing Unit Tests
# -----------------------------------------------------------------------------

def test_extract_citations_from_text_ranges_and_single_lines():
    """Verify regex extraction of [file:line-range] citations from model text."""
    text = (
        "Order processing is implemented in [services/order.py:10-35] and validates "
        "cart contents via [services/cart.py:5-18]. The entry point is at [app/main.py:42]."
    )
    citations = extract_citations_from_text(text)

    assert len(citations) == 3

    c1 = citations[0]
    assert c1.file_path == "services/order.py"
    assert c1.start_line == 10
    assert c1.end_line == 35
    assert c1.label == "services/order.py:10-35"

    c2 = citations[1]
    assert c2.file_path == "services/cart.py"
    assert c2.start_line == 5
    assert c2.end_line == 18
    assert c2.label == "services/cart.py:5-18"

    c3 = citations[2]
    assert c3.file_path == "app/main.py"
    assert c3.start_line == 42
    assert c3.end_line == 42
    assert c3.label == "app/main.py:42"


def test_extract_citations_deduplicates_repeated_references():
    """Verify citations referring to the same file and lines are deduplicated."""
    text = (
        "Calculations are done in [calc.py:10-20]. "
        "As noted earlier in [calc.py:10-20], the result is returned."
    )
    citations = extract_citations_from_text(text)
    assert len(citations) == 1
    assert citations[0].label == "calc.py:10-20"


# -----------------------------------------------------------------------------
# 2. Prompt Builder & Token Budgeting
# -----------------------------------------------------------------------------

def test_build_chat_prompt_enforces_citations_and_unanswerable_rules():
    """Verify system instructions enforce [file:line-range] citation and honesty rules."""
    chunks = [
        RetrievedChunk(
            chunk_id="c1",
            content="def add(a, b):\n    return a + b",
            file_path="math.py",
            symbol_name="add",
            entity_type="function",
            start_line=1,
            end_line=2,
            similarity=0.9,
            boosted_score=0.9,
        )
    ]

    messages = build_chat_prompt(
        query="How does add work?",
        history=[],
        retrieved_chunks=chunks,
        graph_context_summary="Primary chunk retrieved.",
        context_size=4096,
    )

    assert len(messages) == 2
    system_msg = messages[0]["content"]
    user_msg = messages[1]["content"]

    # Verify Citation rule
    assert "STRICT CITATIONS" in system_msg
    assert "[file_path:start_line-end_line]" in system_msg

    # Verify Honesty / unanswerable rule
    assert "Not enough information in the repository to answer this question" in system_msg

    # Verify Code Context enclosure
    assert "<<<REPOSITORY_CODE_CONTEXT_START>>>" in user_msg
    assert "math.py:1-2" in user_msg
    assert "return a + b" in user_msg


def test_build_chat_prompt_token_budget_truncation():
    """Verify that oversized context is truncated to fit the configured token budget."""
    # Create chunks with 5,000 characters
    oversized_chunks = [
        RetrievedChunk(
            chunk_id=f"c_{i}",
            content="X" * 1000,
            file_path=f"file_{i}.py",
            symbol_name=f"func_{i}",
            entity_type="function",
            start_line=1,
            end_line=50,
            similarity=0.8,
            boosted_score=0.8,
        )
        for i in range(10)
    ]

    # Constrained context size (approx 1000 context tokens = 3500 chars)
    messages = build_chat_prompt(
        query="Summary please",
        history=[],
        retrieved_chunks=oversized_chunks,
        graph_context_summary="",
        context_size=1800,
    )

    user_msg = messages[-1]["content"]
    assert len(user_msg) < 4000
    assert "truncated" in user_msg or "file_0.py" in user_msg


# -----------------------------------------------------------------------------
# 3. Chat Engine Integration Tests
# -----------------------------------------------------------------------------

class MockChatClient(LLMClient):
    """Mock LLM client configured with realistic responses for chat verification."""

    def __init__(self, response_text: str):
        self.model_name = "mock-chat-model"
        self.response_text = response_text
        self.last_messages = []

    async def chat(self, messages, response_schema=None, schema=None, temperature=0.1):
        self.last_messages = list(messages)
        return LLMResponse(
            content=self.response_text,
            model_name="mock-chat-model",
            prompt_tokens=200,
            completion_tokens=60,
            total_tokens=260,
            latency_ms=55,
            tokens_per_second=28.0,
        )

    async def health_check(self):
        return {"status": "healthy"}


@pytest.mark.asyncio
async def test_chat_engine_grounded_answer_with_citations(test_db, temp_chroma_dir):
    """
    CRITICAL TEST FOR PHASE 9D:
    Verify grounded Q&A where the model cites [file:line-range] sources,
    and the engine parses them into structured citation objects.
    """
    project_id = "test_chat_proj"
    project = Project(id=project_id, name="Chat Project", path="/mock/chat")
    test_db.add(project)
    test_db.commit()

    settings = Settings(CHROMA_PERSIST_DIR=temp_chroma_dir)
    embedder = DeterministicEmbedder(dimension=384)
    store = ChromaStoreManager(settings)

    # Index chunks in ChromaDB
    chunks = [
        CodeChunk(
            chunk_id=f"{project_id}:calc:add",
            content="def add(a: int, b: int) -> int:\n    return a + b",
            file_path="calculator.py",
            project_id=project_id,
            start_line=15,
            end_line=25,
            symbol_name="add",
            entity_type="function",
        )
    ]
    await store.index_chunks(project_id, chunks, embedder)

    retriever = RepositoryRetriever(settings=settings, embedder=embedder, store_manager=store)

    model_answer = (
        "Addition is handled by the `add` function in [calculator.py:15-25]. "
        "It accepts two integer parameters and returns their arithmetic sum."
    )
    mock_client = MockChatClient(response_text=model_answer)

    engine = RepositoryChatEngine(
        settings=settings,
        client=mock_client,
        retriever=retriever,
        store_manager=store,
        embedder=embedder,
    )

    response = await engine.chat(
        project_id=project_id,
        message="Where is addition implemented and how does it work?",
        db=test_db,
    )

    assert response.project_id == project_id
    assert "calculator.py:15-25" in response.answer
    assert response.has_sufficient_context is True
    assert len(response.citations) == 1
    assert response.citations[0].file_path == "calculator.py"
    assert response.citations[0].start_line == 15
    assert response.citations[0].end_line == 25
    assert len(response.retrieved_chunks) > 0


@pytest.mark.asyncio
async def test_chat_engine_honest_unanswerable_detection(test_db, temp_chroma_dir):
    """
    CRITICAL TEST FOR PHASE 9D:
    Verify that when asked an unanswerable question with no repository context,
    the model responds that there is not enough information, and the engine
    flags has_sufficient_context = False.
    """
    project_id = "test_unanswerable_proj"
    project = Project(id=project_id, name="Unanswerable Project", path="/mock/empty")
    test_db.add(project)
    test_db.commit()

    settings = Settings(CHROMA_PERSIST_DIR=temp_chroma_dir)
    embedder = DeterministicEmbedder(dimension=384)
    store = ChromaStoreManager(settings)

    model_answer = (
        "Not enough information in the repository to answer this question. "
        "There are no cryptocurrency mining or blockchain modules defined in this codebase."
    )
    mock_client = MockChatClient(response_text=model_answer)

    retriever = RepositoryRetriever(settings=settings, embedder=embedder, store_manager=store)
    engine = RepositoryChatEngine(
        settings=settings,
        client=mock_client,
        retriever=retriever,
        store_manager=store,
        embedder=embedder,
    )

    response = await engine.chat(
        project_id=project_id,
        message="How is cryptocurrency mining configured?",
        db=test_db,
    )

    assert "Not enough information" in response.answer
    assert response.has_sufficient_context is False
    assert len(response.citations) == 0


# -----------------------------------------------------------------------------
# 4. FastAPI Chat Endpoint Workflow Test
# -----------------------------------------------------------------------------

def test_api_chat_endpoint_workflow(client: TestClient):
    """Verify POST /projects/{project_id}/chat endpoint returns valid response schema."""
    from tests.conftest import create_in_memory_zip

    zip_buf = create_in_memory_zip({"main.py": "def main():\n    return 42\n"})
    up_res = client.post(
        "/projects/upload",
        files={"file": ("test_repo.zip", zip_buf, "application/zip")},
    )
    assert up_res.status_code == 201
    project_id = up_res.json()["project_id"]

    model_reply = "The main entry point is defined in [main.py:1-10]."


    with patch(
        "app.rag.chat.RepositoryChatEngine.chat",
        new_callable=AsyncMock,
    ) as mock_chat:
        from app.rag.chat import ChatResponse
        mock_chat.return_value = ChatResponse(
            project_id=project_id,
            query="Where is entry point?",
            answer=model_reply,
            citations=[
                CitationItem(file_path="main.py", start_line=1, end_line=10, label="main.py:1-10")
            ],
            retrieved_chunks=[],
            graph_context_summary="Primary chunk",
            has_sufficient_context=True,
            latency_ms=80,
            tokens_used=120,
        )

        resp = client.post(
            f"/projects/{project_id}/chat",
            json={
                "message": "Where is entry point?",
                "history": [],
                "top_k": 3,
                "enable_graph_expansion": True,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == project_id
        assert "main.py:1-10" in data["answer"]
        assert len(data["citations"]) == 1
        assert data["citations"][0]["file_path"] == "main.py"
        assert data["has_sufficient_context"] is True


def test_api_chat_endpoint_404_for_unknown_project(client: TestClient):
    """Verify 404 response when querying a non-existent project ID."""
    resp = client.post(
        "/projects/non_existent_project_999/chat",
        json={"message": "Hello"},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
