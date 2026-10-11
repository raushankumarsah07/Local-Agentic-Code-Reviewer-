"""
backend/app/rag/knowledge_base.py

Knowledge Base Manager for Phase 9c.
Loads, chunks, and indexes authoritative security & best practice documentation
from docs/knowledge/ into a dedicated ChromaDB collection ('knowledge_base').
Provides grounded guidance retrieval for explaining security and code findings.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.rag.embedder import BaseEmbedder, get_embedder
from app.rag.vector_store import ChromaStoreManager

logger = logging.getLogger(__name__)

# Known topic mappings to optimize targeted retrieval for static analysis rules
RULE_TOPIC_MAPPINGS = {
    "hardcoded_secrets": "hardcoded_secrets",
    "secret": "hardcoded_secrets",
    "api_key": "hardcoded_secrets",
    "sql_injection": "sql_injection",
    "sql": "sql_injection",
    "b608": "sql_injection",  # Bandit hardcoded SQL
    "command_injection": "command_injection",
    "shell_true": "command_injection",
    "subprocess": "command_injection",
    "b602": "command_injection",  # Bandit subprocess shell=True
    "insecure_deserialization": "insecure_deserialization",
    "pickle": "insecure_deserialization",
    "yaml_unsafe": "insecure_deserialization",
    "b301": "insecure_deserialization",  # Bandit pickle
    "eval_exec": "command_injection",
    "b102": "command_injection",  # Bandit exec
    "b307": "command_injection",  # Bandit eval
    "authentication": "authentication_basics",
    "password": "authentication_basics",
    "complexity": "complexity_guidance",
    "cyclomatic": "complexity_guidance",
    "long_function": "complexity_guidance",
}


class KnowledgeChunk(BaseModel):
    """Container for a single markdown chunk from the knowledge base."""
    chunk_id: str
    content: str
    topic: str
    doc_title: str
    section_title: str
    file_path: str
    char_count: int


class RetrievedKnowledgeChunk(BaseModel):
    """Result of querying the knowledge base vector store."""
    chunk_id: str
    content: str
    topic: str
    doc_title: str
    section_title: str
    file_path: str
    similarity: float = Field(0.0, description="Cosine similarity score [0.0 - 1.0]")


def resolve_knowledge_base_dir(configured_path: Optional[Path] = None) -> Path:
    """
    Locate the docs/knowledge directory across various execution roots
    (repository root, backend subfolder, or test fixtures).
    """
    candidates = []
    if configured_path:
        candidates.append(Path(configured_path))

    # Candidate: Relative to current working directory
    candidates.append(Path.cwd() / "docs" / "knowledge")
    candidates.append(Path.cwd().parent / "docs" / "knowledge")

    # Candidate: Relative to this file location (backend/app/rag/knowledge_base.py -> repo root)
    file_root = Path(__file__).resolve().parents[3]
    candidates.append(file_root / "docs" / "knowledge")

    for path in candidates:
        if path.exists() and path.is_dir():
            return path.resolve()

    # Default fallback
    return candidates[0] if candidates else Path("docs/knowledge")


def chunk_markdown_file(
    file_path: Path,
    max_chunk_chars: int = 1500,
) -> List[KnowledgeChunk]:
    """
    Parse a Markdown file into topical section chunks.
    Preserves document title and section headings in chunk content for contextual embedding.
    """
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as err:
        logger.error("Failed to read knowledge file %s: %s", file_path, err)
        return []

    topic = file_path.stem

    # Extract Document Title from '# Title'
    doc_title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    doc_title = doc_title_match.group(1).strip() if doc_title_match else topic.replace("_", " ").title()

    chunks: List[KnowledgeChunk] = []

    # Split into sections based on '## Heading'
    sections = re.split(r"\n(?=##\s+)", text)

    chunk_idx = 0
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue

        # Extract section header
        sec_header_match = re.search(r"^##\s+(.+)$", sec, re.MULTILINE)
        section_title = sec_header_match.group(1).strip() if sec_header_match else "General"

        # If section is small enough, keep as single chunk
        if len(sec) <= max_chunk_chars:
            header_prefix = f"# {doc_title} > ## {section_title}\n\n"
            full_content = header_prefix + sec if not sec.startswith("#") else sec
            chunk_idx += 1
            chunks.append(
                KnowledgeChunk(
                    chunk_id=f"kb:{topic}:{chunk_idx}",
                    content=full_content.strip(),
                    topic=topic,
                    doc_title=doc_title,
                    section_title=section_title,
                    file_path=str(file_path),
                    char_count=len(full_content),
                )
            )
        else:
            # Sub-split large section by '### ' or paragraphs
            subsections = re.split(r"\n(?=###\s+)", sec)
            for sub in subsections:
                sub = sub.strip()
                if not sub:
                    continue

                sub_header_match = re.search(r"^###\s+(.+)$", sub, re.MULTILINE)
                sub_title = sub_header_match.group(1).strip() if sub_header_match else section_title

                header_prefix = f"# {doc_title} > ## {section_title} > {sub_title}\n\n"
                full_content = header_prefix + sub
                chunk_idx += 1
                chunks.append(
                    KnowledgeChunk(
                        chunk_id=f"kb:{topic}:{chunk_idx}",
                        content=full_content.strip(),
                        topic=topic,
                        doc_title=doc_title,
                        section_title=sub_title,
                        file_path=str(file_path),
                        char_count=len(full_content),
                    )
                )

    return chunks


class KnowledgeBaseManager:
    """
    Manages indexing and retrieval for authoritative security guidelines,
    CWE/OWASP mitigations, and Python architecture standards in ChromaDB.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        embedder: Optional[BaseEmbedder] = None,
        store_manager: Optional[ChromaStoreManager] = None,
    ):
        self.settings = settings or get_settings()
        self.embedder = embedder or get_embedder(self.settings)
        self.store = store_manager or ChromaStoreManager(self.settings)
        self.collection_name = getattr(self.settings, "KNOWLEDGE_BASE_COLLECTION", "knowledge_base")

    def get_collection(self):
        """Retrieve the dedicated knowledge base ChromaDB collection."""
        return self.store.get_or_create_knowledge_collection(self.collection_name)

    async def index_knowledge_base(
        self,
        force: bool = False,
        kb_dir: Optional[Path] = None,
    ) -> int:
        """
        Scan all markdown files in the knowledge directory, chunk them,
        generate embeddings, and index into the dedicated ChromaDB collection.
        """
        collection = self.get_collection()

        # Skip if already indexed unless force=True
        if not force and collection.count() > 0:
            logger.info("Knowledge base collection already indexed with %d chunks.", collection.count())
            return collection.count()

        resolved_dir = resolve_knowledge_base_dir(kb_dir or getattr(self.settings, "KNOWLEDGE_BASE_DIR", None))
        if not resolved_dir.exists():
            logger.warning("Knowledge base directory %s does not exist; skipping indexing.", resolved_dir)
            return 0

        md_files = sorted(resolved_dir.glob("*.md"))
        if not md_files:
            logger.warning("No .md files found in knowledge directory %s.", resolved_dir)
            return 0

        all_chunks: List[KnowledgeChunk] = []
        for file_path in md_files:
            file_chunks = chunk_markdown_file(file_path)
            all_chunks.extend(file_chunks)

        if not all_chunks:
            return 0

        logger.info("Indexing %d knowledge base chunks from %s...", len(all_chunks), resolved_dir)

        # Generate vector embeddings
        texts = [c.content for c in all_chunks]
        embeddings = await self.embedder.embed_documents(texts)

        ids = [c.chunk_id for c in all_chunks]
        documents = [c.content for c in all_chunks]
        metadatas = [
            {
                "topic": c.topic,
                "doc_title": c.doc_title,
                "section_title": c.section_title,
                "file_path": c.file_path,
                "char_count": int(c.char_count),
            }
            for c in all_chunks
        ]

        # Upsert in batches of 50
        batch_size = 50
        for i in range(0, len(ids), batch_size):
            collection.upsert(
                ids=ids[i : i + batch_size],
                embeddings=embeddings[i : i + batch_size],
                documents=documents[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size],
            )

        logger.info("Successfully indexed %d knowledge chunks in ChromaDB.", len(all_chunks))
        return len(all_chunks)

    async def query_knowledge_base(
        self,
        query: str,
        top_k: int = 2,
        topic_filter: Optional[str] = None,
    ) -> List[RetrievedKnowledgeChunk]:
        """
        Perform cosine similarity search against the knowledge base collection.
        Automatically indexes the knowledge base if the collection is empty.
        """
        query_clean = query.strip()
        if not query_clean:
            return []

        collection = self.get_collection()
        if collection.count() == 0:
            await self.index_knowledge_base()

        if collection.count() == 0:
            return []

        # Embed user query
        query_embedding = await self.embedder.embed_query(query_clean)

        where_clause = {"topic": topic_filter} if topic_filter else None

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count()),
            where=where_clause,
        )

        retrieved: List[RetrievedKnowledgeChunk] = []
        if not results or not results["ids"] or not results["ids"][0]:
            return []

        ids = results["ids"][0]
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        distances = results.get("distances", [[0.0] * len(ids)])[0]

        for cid, doc, meta, dist in zip(ids, docs, metas, distances):
            similarity = round(max(0.0, 1.0 - float(dist)), 4)
            retrieved.append(
                RetrievedKnowledgeChunk(
                    chunk_id=cid,
                    content=doc,
                    topic=meta.get("topic", "general"),
                    doc_title=meta.get("doc_title", "Knowledge Base"),
                    section_title=meta.get("section_title", "Guidance"),
                    file_path=meta.get("file_path", ""),
                    similarity=similarity,
                )
            )

        return retrieved

    def format_knowledge_context(self, chunks: List[RetrievedKnowledgeChunk]) -> str:
        """
        Format retrieved knowledge chunks into structured, authoritative guidance
        to inject into LLM prompts.
        """
        if not chunks:
            return ""

        formatted_sections: List[str] = []
        for i, chunk in enumerate(chunks, 1):
            formatted_sections.append(
                f"[KNOWLEDGE BASE GUIDANCE #{i}: {chunk.doc_title} > {chunk.section_title}]\n"
                f"{chunk.content.strip()}"
            )

        return "\n\n".join(formatted_sections)

    async def get_guidance_for_finding(
        self,
        finding_type: str,
        finding_title: str,
        finding_rule_id: Optional[str] = None,
        top_k: int = 2,
    ) -> Optional[str]:
        """
        High-level helper: inspects finding metadata, identifies target topic,
        and retrieves formatted authoritative guidance.
        """
        # Determine topic hint if possible
        topic_hint: Optional[str] = None
        search_terms = f"{finding_type} {finding_title} {finding_rule_id or ''}".lower()

        for key, topic in RULE_TOPIC_MAPPINGS.items():
            if key in search_terms:
                topic_hint = topic
                break

        chunks = await self.query_knowledge_base(
            query=f"{finding_title} remediation secure fix {finding_rule_id or ''}",
            top_k=top_k,
            topic_filter=topic_hint,
        )

        # Fallback without topic filter if none found
        if not chunks and topic_hint:
            chunks = await self.query_knowledge_base(
                query=f"{finding_title} remediation secure fix",
                top_k=top_k,
            )

        if not chunks:
            return None

        return self.format_knowledge_context(chunks)
