"""
backend/app/rag/__init__.py

RAG (Retrieval-Augmented Generation) Module for Phase 9.
Provides AST-aware chunking, local vector embedding, persistent ChromaDB indexing,
and repository retrieval.
"""

from app.rag.chunker import (
    CodeChunk,
    ASTChunker,
    chunk_file,
)
from app.rag.embedder import (
    BaseEmbedder,
    LlamaCppEmbedder,
    OllamaEmbedder,
    DeterministicEmbedder,
    get_embedder,
)
from app.rag.retriever import (
    RetrievedChunk,
    RetrievalResult,
    RepositoryRetriever,
    extract_query_identifiers,
    apply_keyword_boost,
)
from app.rag.knowledge_base import (
    KnowledgeChunk,
    RetrievedKnowledgeChunk,
    KnowledgeBaseManager,
    chunk_markdown_file,
    resolve_knowledge_base_dir,
)
from app.rag.vector_store import (
    ChromaStoreManager,
    sanitize_collection_name,
)

__all__ = [
    "CodeChunk",
    "ASTChunker",
    "chunk_file",
    "BaseEmbedder",
    "LlamaCppEmbedder",
    "OllamaEmbedder",
    "DeterministicEmbedder",
    "get_embedder",
    "ChromaStoreManager",
    "sanitize_collection_name",
    "RetrievedChunk",
    "RetrievalResult",
    "RepositoryRetriever",
    "extract_query_identifiers",
    "apply_keyword_boost",
    "KnowledgeChunk",
    "RetrievedKnowledgeChunk",
    "KnowledgeBaseManager",
    "chunk_markdown_file",
    "resolve_knowledge_base_dir",
]


