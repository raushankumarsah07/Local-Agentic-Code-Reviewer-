"""
backend/app/rag/vector_store.py

Persistent ChromaDB Vector Store Manager for Phase 9a.
Maintains one isolated persistent collection per project with cosine distance indexing.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import chromadb
from chromadb.api.models.Collection import Collection

from app.config import Settings, get_settings
from app.rag.chunker import CodeChunk
from app.rag.embedder import BaseEmbedder, get_embedder

logger = logging.getLogger(__name__)


def sanitize_collection_name(project_id: str) -> str:
    """
    Generate a valid ChromaDB collection name (3-63 characters, alphanumeric, underscores).
    Chroma requirements: length in [3, 63], matches ^[a-zA-Z0-9][a-zA-Z0-9._-]*[a-zA-Z0-9]$
    """
    clean_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(project_id).strip())
    name = f"proj_{clean_id}"[:60]
    # Ensure starts and ends with alphanumeric
    if not name[0].isalnum():
        name = "p" + name[1:]
    if not name[-1].isalnum():
        name = name[:-1] + "0"
    return name


class ChromaStoreManager:
    """
    Manager for project vector collections backed by persistent ChromaDB.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.persist_dir = Path(self.settings.CHROMA_PERSIST_DIR)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.persist_dir.resolve()))

    def get_or_create_project_collection(self, project_id: str) -> Collection:
        """Fetch or initialize a project's dedicated ChromaDB collection."""
        name = sanitize_collection_name(project_id)
        return self.client.get_or_create_collection(
            name=name,
            metadata={"project_id": str(project_id), "hnsw:space": "cosine"},
        )

    def get_or_create_knowledge_collection(self, collection_name: Optional[str] = None) -> Collection:
        """Fetch or initialize the isolated ChromaDB collection for knowledge base documentation."""
        name = collection_name or getattr(self.settings, "KNOWLEDGE_BASE_COLLECTION", "knowledge_base")
        return self.client.get_or_create_collection(
            name=name,
            metadata={"category": "knowledge_base", "hnsw:space": "cosine"},
        )

    async def index_chunks(
        self,
        project_id: str,
        chunks: List[CodeChunk],
        embedder: Optional[BaseEmbedder] = None,
    ) -> int:
        """
        Embed and upsert code chunks into the project's vector collection.
        Returns the count of chunks indexed.
        """
        if not chunks:
            return 0

        active_embedder = embedder or get_embedder(self.settings)
        collection = self.get_or_create_project_collection(project_id)

        # 1. Compute embeddings
        texts = [c.content for c in chunks]
        embeddings = await active_embedder.embed_documents(texts)

        # 2. Prepare payload
        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for c in chunks:
            ids.append(c.chunk_id)
            documents.append(c.content)
            metadatas.append({
                "project_id": str(c.project_id),
                "file_path": c.file_path,
                "symbol_name": c.symbol_name or "",
                "entity_type": c.entity_type,
                "start_line": int(c.start_line),
                "end_line": int(c.end_line),
                "language": c.language,
                "parent_name": c.parent_name or "",
                "char_count": int(c.char_count),
                "token_estimate": int(c.token_estimate),
            })

        # 3. Upsert into collection (batches of 100 to respect memory constraints)
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            collection.upsert(
                ids=ids[i : i + batch_size],
                embeddings=embeddings[i : i + batch_size],
                documents=documents[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size],
            )

        logger.info(
            "Successfully indexed %d chunks in collection '%s' for project '%s'",
            len(chunks),
            collection.name,
            project_id,
        )
        return len(chunks)

    async def query_similar_chunks(
        self,
        project_id: str,
        query: str,
        top_k: int = 5,
        embedder: Optional[BaseEmbedder] = None,
        where_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform cosine similarity search for top-k relevant chunks given a text query.
        Returns list of matched chunks with cosine similarity score in [0.0, 1.0].
        """
        if not query or not query.strip():
            return []

        active_embedder = embedder or get_embedder(self.settings)
        collection = self.get_or_create_project_collection(project_id)

        if collection.count() == 0:
            return []

        # Generate query vector
        query_vector = await active_embedder.embed_query(query)

        # Query ChromaDB
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=min(top_k, collection.count()),
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        matches: List[Dict[str, Any]] = []
        if results and "ids" in results and results["ids"]:
            ids_list = results["ids"][0]
            docs_list = results["documents"][0] if "documents" in results else []
            meta_list = results["metadatas"][0] if "metadatas" in results else []
            dist_list = results["distances"][0] if "distances" in results else []

            for idx, chunk_id in enumerate(ids_list):
                distance = dist_list[idx] if idx < len(dist_list) else 1.0
                # In cosine space, cosine_distance = 1 - cosine_similarity
                similarity = max(0.0, min(1.0, 1.0 - distance))
                matches.append({
                    "chunk_id": chunk_id,
                    "content": docs_list[idx] if idx < len(docs_list) else "",
                    "metadata": meta_list[idx] if idx < len(meta_list) else {},
                    "distance": round(distance, 4),
                    "similarity": round(similarity, 4),
                })

        return matches

    def count_chunks(self, project_id: str) -> int:
        """Return the number of indexed chunks in the project collection."""
        try:
            col = self.get_or_create_project_collection(project_id)
            return col.count()
        except Exception:
            return 0

    def delete_project_collection(self, project_id: str) -> bool:
        """Delete a project's collection from ChromaDB."""
        name = sanitize_collection_name(project_id)
        try:
            self.client.delete_collection(name=name)
            logger.info("Deleted collection '%s' for project '%s'", name, project_id)
            return True
        except Exception as e:
            logger.debug("Collection '%s' does not exist or failed deletion: %s", name, e)
            return False
