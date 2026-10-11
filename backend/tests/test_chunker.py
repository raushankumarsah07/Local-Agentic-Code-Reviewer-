"""
Unit tests for Phase 9a: AST-Aware Chunker, Embedder, and Persistent ChromaDB Vector Store.
"""

import tempfile
import shutil
from pathlib import Path
import pytest
from app.config import Settings
from app.rag.chunker import ASTChunker, chunk_file, CodeChunk
from app.rag.embedder import DeterministicEmbedder, get_embedder
from app.rag.vector_store import ChromaStoreManager, sanitize_collection_name


@pytest.fixture
def temp_chroma_dir():
    temp_dir = Path(tempfile.mkdtemp(prefix="test_chroma_"))
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


# -----------------------------------------------------------------------------
# 1. AST Chunker: Functions, Classes, Methods
# -----------------------------------------------------------------------------

def test_ast_chunker_extracts_standalone_functions():
    """Verify that standalone functions produce individual chunks with accurate metadata."""
    code = (
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n\n"
        "def subtract(a: int, b: int) -> int:\n"
        "    return a - b\n"
    )
    chunker = ASTChunker(size_cap_chars=1000)
    chunks = chunker.chunk_python_code(code, file_path="math_ops.py", project_id="proj_test")

    assert len(chunks) == 2
    c1, c2 = chunks[0], chunks[1]

    assert c1.symbol_name == "add"
    assert c1.entity_type == "function"
    assert c1.start_line == 1
    assert c1.end_line == 2
    assert "return a + b" in c1.content

    assert c2.symbol_name == "subtract"
    assert c2.entity_type == "function"
    assert c2.start_line == 4
    assert c2.end_line == 5
    assert "return a - b" in c2.content


def test_ast_chunker_extracts_classes_and_methods():
    """Verify that class definitions produce a header chunk and distinct method chunks."""
    code = (
        'class Calculator:\n'
        '    """Arithmetic calculation engine."""\n'
        '    def __init__(self):\n'
        '        self.total = 0\n\n'
        '    def multiply(self, factor: int):\n'
        '        self.total *= factor\n'
        '        return self.total\n'
    )
    chunker = ASTChunker(size_cap_chars=1000)
    chunks = chunker.chunk_python_code(code, file_path="calc.py", project_id="proj_test")

    # Expect: Class header chunk + __init__ method + multiply method
    assert len(chunks) >= 2
    class_chunk = next(c for c in chunks if c.entity_type == "class")
    assert class_chunk.symbol_name == "Calculator"
    assert "Arithmetic calculation engine" in class_chunk.content

    methods = [c for c in chunks if c.entity_type == "method"]
    assert len(methods) == 2
    method_names = [m.symbol_name for m in methods]
    assert "Calculator.__init__" in method_names
    assert "Calculator.multiply" in method_names

    multiply_chunk = next(m for m in methods if m.symbol_name == "Calculator.multiply")
    assert multiply_chunk.parent_name == "Calculator"
    assert multiply_chunk.start_line == 6
    assert multiply_chunk.end_line == 8
    assert "self.total *= factor" in multiply_chunk.content


def test_ast_chunker_module_docstring():
    """Verify that top-level module docstrings are captured as module chunks."""
    code = (
        '"""\n'
        'Module utility for parsing transactions.\n'
        'Contains bank helper routines.\n'
        '"""\n\n'
        'def process():\n'
        '    pass\n'
    )
    chunker = ASTChunker(size_cap_chars=1000)
    chunks = chunker.chunk_python_code(code, file_path="tx.py", project_id="proj_test")

    assert len(chunks) == 2
    mod_chunk = next(c for c in chunks if c.entity_type == "module")
    assert "parsing transactions" in mod_chunk.content
    assert mod_chunk.start_line == 1


# -----------------------------------------------------------------------------
# 2. Size Cap Splitting
# -----------------------------------------------------------------------------

def test_ast_chunker_enforces_size_cap():
    """Verify that an oversized function is split into capped subchunks."""
    # Create a 200-line function that will exceed 400 characters
    fn_lines = ["def huge_procedure():\n"]
    for i in range(1, 50):
        fn_lines.append(f"    step_{i} = execute_step({i}, 'parameter_data')\n")
    big_code = "".join(fn_lines)

    chunker = ASTChunker(size_cap_chars=400, subchunk_overlap_chars=50)
    chunks = chunker.chunk_python_code(big_code, file_path="huge.py", project_id="proj_test")

    assert len(chunks) > 1
    for c in chunks:
        # All subchunks must respect the cap (+ header overhead)
        assert len(c.content) <= 550
        assert "huge_procedure" in c.symbol_name


# -----------------------------------------------------------------------------
# 3. Graceful Fallbacks (Syntax Error & Non-Python)
# -----------------------------------------------------------------------------

def test_ast_chunker_syntax_error_fallback():
    """Verify that deliberate syntax error does not crash and falls back to text blocks."""
    broken_code = (
        "def invalid_syntax(\n"
        "    if True\n"
        "        missing_colons everywhere\n"
    )
    chunker = ASTChunker(size_cap_chars=500)
    chunks = chunker.chunk_python_code(broken_code, file_path="broken.py", project_id="proj_test")

    assert len(chunks) >= 1
    assert chunks[0].entity_type == "raw_block"
    assert "missing_colons" in chunks[0].content


def test_chunk_file_non_python():
    """Verify chunk_file correctly chunks non-python text/markdown files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        doc = root / "README.md"
        doc.write_text("# Documentation\n\nThis is a sample project.\n" * 10, encoding="utf-8")

        chunks = chunk_file(doc, root, project_id="proj_test", size_cap_chars=200)
        assert len(chunks) >= 1
        assert chunks[0].language == "md"
        assert chunks[0].entity_type == "raw_block"


# -----------------------------------------------------------------------------
# 4. Embedder and ChromaDB Persistent Indexing
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deterministic_embedder_cosine_similarity():
    """Verify that DeterministicEmbedder generates normalized vectors with expected similarity."""
    embedder = DeterministicEmbedder(dimension=384)
    assert embedder.dimension == 384

    doc1 = "def authenticate_user(username, password): pass"
    doc2 = "def login_user(username, password): pass"
    unrelated = "def compute_matrix_determinant(matrix): pass"

    embs = await embedder.embed_documents([doc1, doc2, unrelated])
    assert len(embs) == 3
    assert len(embs[0]) == 384

    # Calculate cosine similarity as dot product of unit vectors
    def dot_product(v1, v2):
        return sum(a * b for a, b in zip(v1, v2))

    sim_related = dot_product(embs[0], embs[1])
    sim_unrelated = dot_product(embs[0], embs[2])

    assert sim_related > sim_unrelated


@pytest.mark.asyncio
async def test_chroma_store_manager_indexing_and_query(temp_chroma_dir: Path):
    """Test ChromaStoreManager upsert and top-k cosine similarity retrieval."""
    test_settings = Settings(
        CHROMA_PERSIST_DIR=temp_chroma_dir,
        EMBEDDING_BACKEND="deterministic",
    )
    store = ChromaStoreManager(settings=test_settings)
    embedder = DeterministicEmbedder(dimension=384)

    test_chunks = [
        CodeChunk(
            chunk_id="chk_auth",
            project_id="test_proj_123",
            file_path="auth.py",
            symbol_name="login",
            entity_type="function",
            start_line=10,
            end_line=25,
            language="python",
            content="def login(credentials):\n    # authenticate user session\n    return token",
            char_count=68,
        ),
        CodeChunk(
            chunk_id="chk_sql",
            project_id="test_proj_123",
            file_path="db.py",
            symbol_name="execute_query",
            entity_type="function",
            start_line=30,
            end_line=45,
            language="python",
            content="def execute_query(sql):\n    cursor.execute(sql)\n    return cursor.fetchall()",
            char_count=65,
        ),
    ]

    # Index chunks
    indexed_count = await store.index_chunks(
        project_id="test_proj_123",
        chunks=test_chunks,
        embedder=embedder,
    )
    assert indexed_count == 2
    assert store.count_chunks("test_proj_123") == 2

    # Query top-k
    results = await store.query_similar_chunks(
        project_id="test_proj_123",
        query="user login authentication session",
        top_k=2,
        embedder=embedder,
    )
    assert len(results) == 2
    # The login function should rank highest
    top_hit = results[0]
    assert top_hit["chunk_id"] == "chk_auth"
    assert top_hit["metadata"]["symbol_name"] == "login"
    assert top_hit["similarity"] >= 0.0

    # Delete collection
    deleted = store.delete_project_collection("test_proj_123")
    assert deleted is True
