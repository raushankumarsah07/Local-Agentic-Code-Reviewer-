"""
backend/app/rag/retriever.py

Repository Retriever for Phase 9b.
Combines:
1. Top-k Cosine Similarity search over ChromaDB code vectors.
2. Keyword Boost for exact identifier and symbol name matches.
3. Graph Expansion pulling callers, callees, and importing modules from the architectural graph.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import CodeEntity, GraphEdge
from app.db.session import SessionLocal
from app.rag.embedder import BaseEmbedder, get_embedder
from app.rag.vector_store import ChromaStoreManager

logger = logging.getLogger(__name__)

# Stopwords to ignore when extracting code identifiers from questions
QUERY_STOPWORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "can", "could", "should", "would", "will", "shall",
    "how", "what", "where", "when", "why", "who", "which",
    "code", "file", "function", "class", "method", "module", "handled", "handling",
    "implemented", "defined", "used", "located", "show", "find", "explain", "get",
}


class RetrievedChunk(BaseModel):
    """Container for a single retrieved chunk with scoring and relationship metadata."""
    chunk_id: str
    content: str
    file_path: str
    symbol_name: Optional[str] = None
    entity_type: str
    start_line: int
    end_line: int
    similarity: float = Field(0.0, description="Raw cosine similarity [0.0 - 1.0]")
    boosted_score: float = Field(0.0, description="Score after keyword matching boost")
    matched_keywords: List[str] = Field(default_factory=list)
    is_expanded: bool = Field(False, description="True if pulled in via graph expansion")
    expansion_type: Optional[str] = Field(None, description="'caller', 'callee', or 'importer'")
    expansion_reason: Optional[str] = Field(None, description="Human explanation of architectural relationship")


class RetrievalResult(BaseModel):
    """Complete retrieval response including primary hits, graph context, and summary."""
    query: str
    project_id: str
    primary_chunks: List[RetrievedChunk]
    expanded_chunks: List[RetrievedChunk]
    all_chunks: List[RetrievedChunk]
    graph_context_summary: str
    total_chunks: int


def extract_query_identifiers(query: str) -> List[str]:
    """
    Extract potential variable, function, class, and module identifiers from a natural language query.
    Extracts snake_case, CamelCase, and alphanumeric code tokens.
    """
    tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", query)
    identifiers: List[str] = []

    for t in tokens:
        clean = t.strip()
        if len(clean) >= 2 and clean.lower() not in QUERY_STOPWORDS:
            identifiers.append(clean)

    return list(dict.fromkeys(identifiers))  # Deduplicate while preserving order


def apply_keyword_boost(
    candidates: List[Dict[str, Any]],
    query_identifiers: List[str],
    symbol_match_boost: float = 0.35,
    file_match_boost: float = 0.20,
    content_match_boost: float = 0.10,
) -> List[RetrievedChunk]:
    """
    Apply additive score boosts for exact identifier matches against candidate chunks.
    Re-ranks candidates by boosted_score.
    """
    boosted_results: List[RetrievedChunk] = []

    for item in candidates:
        raw_sim = float(item.get("similarity", 0.0))
        meta = item.get("metadata", {})
        content = item.get("content", "")
        symbol = str(meta.get("symbol_name") or "")
        file_path = str(meta.get("file_path") or "")

        boost = 0.0
        matched: List[str] = []

        # Check each extracted identifier
        for ident in query_identifiers:
            ident_lower = ident.lower()
            symbol_lower = symbol.lower()
            file_lower = file_path.lower()

            # 1. Exact symbol or base name match (highest boost)
            base_symbol = symbol_lower.split(".")[-1]
            if ident_lower == symbol_lower or ident_lower == base_symbol:
                boost += symbol_match_boost
                matched.append(f"symbol:{ident}")
            elif ident_lower in symbol_lower:
                boost += symbol_match_boost * 0.5
                matched.append(f"subsymbol:{ident}")

            # 2. File path match
            if ident_lower in file_lower:
                boost += file_match_boost
                matched.append(f"file:{ident}")

            # 3. Exact word occurrence in snippet content
            if re.search(rf"\b{re.escape(ident)}\b", content, re.IGNORECASE):
                boost += content_match_boost
                matched.append(f"content:{ident}")

        final_score = round(raw_sim + boost, 4)

        boosted_results.append(
            RetrievedChunk(
                chunk_id=item["chunk_id"],
                content=content,
                file_path=file_path,
                symbol_name=symbol or None,
                entity_type=str(meta.get("entity_type") or "function"),
                start_line=int(meta.get("start_line", 1)),
                end_line=int(meta.get("end_line", 1)),
                similarity=round(raw_sim, 4),
                boosted_score=final_score,
                matched_keywords=list(set(matched)),
                is_expanded=False,
            )
        )

    # Sort descending by boosted score
    boosted_results.sort(key=lambda x: x.boosted_score, reverse=True)
    return boosted_results


class RepositoryRetriever:
    """
    Retrieves repository code chunks using hybrid semantic search,
    exact keyword boosting, and architectural call-graph expansion.
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

    async def retrieve(
        self,
        project_id: str,
        query: str,
        top_k: int = 5,
        db: Optional[Session] = None,
        enable_graph_expansion: bool = True,
        max_expansions: int = 4,
    ) -> RetrievalResult:
        """
        Execute hybrid retrieval pipeline:
        1. Query ChromaDB for top candidates via cosine similarity.
        2. Boost candidates matching exact identifiers from query.
        3. Perform graph expansion to fetch callers, callees, and importers.
        """
        query_clean = query.strip()
        if not query_clean:
            return RetrievalResult(
                query=query,
                project_id=project_id,
                primary_chunks=[],
                expanded_chunks=[],
                all_chunks=[],
                graph_context_summary="Empty query supplied.",
                total_chunks=0,
            )

        # 1. Cosine Vector Search (pull 2x candidates to allow keyword re-ranking)
        candidate_count = max(top_k * 2, 8)
        raw_candidates = await self.store.query_similar_chunks(
            project_id=project_id,
            query=query_clean,
            top_k=candidate_count,
            embedder=self.embedder,
        )

        # 2. Keyword Identifier Boost
        query_idents = extract_query_identifiers(query_clean)
        boosted_chunks = apply_keyword_boost(raw_candidates, query_idents)

        # Select top-k primary chunks
        primary_chunks = boosted_chunks[:top_k]
        primary_ids = {c.chunk_id for c in primary_chunks}

        # 3. Architectural Graph Expansion
        expanded_chunks: List[RetrievedChunk] = []
        expansion_notes: List[str] = []

        if enable_graph_expansion and primary_chunks:
            expanded_chunks, expansion_notes = self._expand_via_graph(
                project_id=project_id,
                primary_chunks=primary_chunks,
                primary_ids=primary_ids,
                db=db,
                max_expansions=max_expansions,
            )

        # 4. Formulate Summary and Combined List
        all_chunks = list(primary_chunks) + list(expanded_chunks)
        summary = self._build_context_summary(
            primary_chunks=primary_chunks,
            expanded_chunks=expanded_chunks,
            expansion_notes=expansion_notes,
            query_idents=query_idents,
        )

        return RetrievalResult(
            query=query_clean,
            project_id=project_id,
            primary_chunks=primary_chunks,
            expanded_chunks=expanded_chunks,
            all_chunks=all_chunks,
            graph_context_summary=summary,
            total_chunks=len(all_chunks),
        )

    def _expand_via_graph(
        self,
        project_id: str,
        primary_chunks: List[RetrievedChunk],
        primary_ids: Set[str],
        db: Optional[Session] = None,
        max_expansions: int = 4,
    ) -> Tuple[List[RetrievedChunk], List[str]]:
        """
        Traverse the call graph and dependency graph to locate:
        - Callers: functions that invoke any primary symbol
        - Callees: functions invoked by any primary symbol
        - Importers: files that import the file of a primary symbol
        """
        expanded: List[RetrievedChunk] = []
        notes: List[str] = []
        seen_ids = set(primary_ids)

        session_created = False
        if db is None:
            db = SessionLocal()
            session_created = True

        try:
            collection = self.store.get_or_create_project_collection(project_id)

            # Pre-load entities and edges for project
            entities = db.query(CodeEntity).filter(CodeEntity.project_id == project_id).all()
            edges = db.query(GraphEdge).filter(GraphEdge.project_id == project_id).all()

            for chunk in primary_chunks:
                if len(expanded) >= max_expansions:
                    break

                symbol = chunk.symbol_name
                file_path = chunk.file_path

                # A. Find Callees (What does this function invoke?)
                # Look up the entity for chunk to read its calls
                chunk_entity = next(
                    (e for e in entities if e.file_path == file_path and (e.name == symbol or (e.parent_name and f"{e.parent_name}.{e.name}" == symbol))),
                    None,
                )

                if chunk_entity and chunk_entity.details:
                    try:
                        details_dict = json.loads(chunk_entity.details)
                        calls_list = details_dict.get("calls", [])
                        for callee_name in calls_list:
                            if len(expanded) >= max_expansions:
                                break
                            base_callee = callee_name.split(".")[-1]
                            # Query ChromaDB collection for the callee chunk
                            callee_res = collection.get(where={"symbol_name": base_callee})
                            if callee_res and callee_res["ids"]:
                                for cid, doc, meta in zip(callee_res["ids"], callee_res["documents"], callee_res["metadatas"]):
                                    if cid not in seen_ids:
                                        seen_ids.add(cid)
                                        reason = f"Callee invoked by {symbol}() in {file_path}:{chunk.start_line}"
                                        expanded.append(
                                            RetrievedChunk(
                                                chunk_id=cid,
                                                content=doc,
                                                file_path=meta.get("file_path", ""),
                                                symbol_name=meta.get("symbol_name"),
                                                entity_type=meta.get("entity_type", "function"),
                                                start_line=int(meta.get("start_line", 1)),
                                                end_line=int(meta.get("end_line", 1)),
                                                similarity=chunk.similarity * 0.85,
                                                boosted_score=chunk.boosted_score * 0.85,
                                                is_expanded=True,
                                                expansion_type="callee",
                                                expansion_reason=reason,
                                            )
                                        )
                                        notes.append(f"Callee '{base_callee}' ({meta.get('file_path')})")
                    except Exception as err:
                        logger.debug("Failed parsing calls for entity %s: %s", symbol, err)

                # B. Find Callers (Who invokes this symbol?)
                if symbol:
                    base_symbol = symbol.split(".")[-1]
                    for ent in entities:
                        if len(expanded) >= max_expansions:
                            break
                        if ent.details and ent.file_path != file_path:
                            try:
                                ent_details = json.loads(ent.details)
                                if any(base_symbol in c or c.endswith(f".{base_symbol}") for c in ent_details.get("calls", [])):
                                    # This entity calls our symbol!
                                    caller_symbol = f"{ent.parent_name}.{ent.name}" if ent.parent_name else ent.name
                                    caller_res = collection.get(where={"symbol_name": caller_symbol})
                                    if caller_res and caller_res["ids"]:
                                        for cid, doc, meta in zip(caller_res["ids"], caller_res["documents"], caller_res["metadatas"]):
                                            if cid not in seen_ids:
                                                seen_ids.add(cid)
                                                reason = f"Caller that invokes {symbol}() from {ent.file_path}:{ent.start_line}"
                                                expanded.append(
                                                    RetrievedChunk(
                                                        chunk_id=cid,
                                                        content=doc,
                                                        file_path=meta.get("file_path", ent.file_path),
                                                        symbol_name=caller_symbol,
                                                        entity_type=meta.get("entity_type", ent.entity_type),
                                                        start_line=int(meta.get("start_line", ent.start_line)),
                                                        end_line=int(meta.get("end_line", ent.end_line)),
                                                        similarity=chunk.similarity * 0.90,
                                                        boosted_score=chunk.boosted_score * 0.90,
                                                        is_expanded=True,
                                                        expansion_type="caller",
                                                        expansion_reason=reason,
                                                    )
                                                )
                                                notes.append(f"Caller '{caller_symbol}' in {ent.file_path}")
                            except Exception:
                                pass

                # C. Find Importers (Which files import this file?)
                for edge in edges:
                    if len(expanded) >= max_expansions:
                        break
                    if edge.target == file_path and edge.source != file_path:
                        # edge.source is an importing module
                        imp_res = collection.get(where={"file_path": edge.source})
                        if imp_res and imp_res["ids"]:
                            cid = imp_res["ids"][0]
                            if cid not in seen_ids:
                                seen_ids.add(cid)
                                doc = imp_res["documents"][0]
                                meta = imp_res["metadatas"][0]
                                reason = f"Module {edge.source} imports {file_path}"
                                expanded.append(
                                    RetrievedChunk(
                                        chunk_id=cid,
                                        content=doc,
                                        file_path=edge.source,
                                        symbol_name=meta.get("symbol_name"),
                                        entity_type=meta.get("entity_type", "module"),
                                        start_line=int(meta.get("start_line", 1)),
                                        end_line=int(meta.get("end_line", 1)),
                                        similarity=chunk.similarity * 0.75,
                                        boosted_score=chunk.boosted_score * 0.75,
                                        is_expanded=True,
                                        expansion_type="importer",
                                        expansion_reason=reason,
                                    )
                                )
                                notes.append(f"Importer module '{edge.source}'")

        finally:
            if session_created:
                db.close()

        return expanded, notes

    def _build_context_summary(
        self,
        primary_chunks: List[RetrievedChunk],
        expanded_chunks: List[RetrievedChunk],
        expansion_notes: List[str],
        query_idents: List[str],
    ) -> str:
        """Create a concise human-readable narrative explaining the retrieved context."""
        parts: List[str] = []
        if primary_chunks:
            primary_symbols = [f"'{c.symbol_name}' ({c.file_path}:{c.start_line})" for c in primary_chunks if c.symbol_name]
            parts.append(f"Retrieved {len(primary_chunks)} primary chunk(s): {', '.join(primary_symbols) if primary_symbols else 'relevant code blocks'}.")

        if query_idents:
            parts.append(f"Exact identifier keyword matches: {', '.join(query_idents)}.")

        if expanded_chunks:
            parts.append(f"Graph expansion added {len(expanded_chunks)} architectural neighbor(s): {', '.join(expansion_notes)}.")
        else:
            parts.append("No additional architectural graph neighbors were required.")

        return " ".join(parts)
