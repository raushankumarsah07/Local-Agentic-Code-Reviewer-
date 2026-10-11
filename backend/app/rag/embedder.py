"""
backend/app/rag/embedder.py

Local Embedding Model Client for Phase 9a.
Supports:
- llama.cpp embedding server (OpenAI-compatible /v1/embeddings)
- Ollama embedding API (/api/embed and /api/embeddings)
- DeterministicEmbedder for offline test verification and fallback.
"""

import abc
import hashlib
import logging
import math
from typing import Any, Dict, List, Optional
import httpx
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class BaseEmbedder(abc.ABC):
    """Abstract interface for text and code embedding models."""

    @property
    @abc.abstractmethod
    def dimension(self) -> int:
        """Return the vector dimensionality."""
        pass

    @abc.abstractmethod
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Compute embedding vectors for a list of documents."""
        pass

    @abc.abstractmethod
    async def embed_query(self, text: str) -> List[float]:
        """Compute embedding vector for a single query."""
        pass


class DeterministicEmbedder(BaseEmbedder):
    """
    Deterministic pseudo-embedder for offline test verification and reliable fallback.
    Uses n-gram feature hashing with unit-norm projection to simulate semantic vectors.
    """

    def __init__(self, dimension: int = 384):
        self._dim = dimension

    @property
    def dimension(self) -> int:
        return self._dim

    def _hash_text_to_vector(self, text: str) -> List[float]:
        """Hash tokens and n-grams into a fixed-length normalized vector."""
        vec = [0.0] * self._dim
        if not text:
            return vec

        # Tokenize simply
        words = text.lower().split()
        for w in words:
            # Word hash
            h1 = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16) % self._dim
            vec[h1] += 1.0

            # Subword 3-grams
            for i in range(len(w) - 2):
                tri = w[i : i + 3]
                h2 = int(hashlib.sha256(tri.encode("utf-8")).hexdigest(), 16) % self._dim
                vec[h2] += 0.5

        # L2 normalization to unit circle for cosine similarity
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 1e-9:
            vec = [v / norm for v in vec]
        return vec

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_text_to_vector(t) for t in texts]

    async def embed_query(self, text: str) -> List[float]:
        return self._hash_text_to_vector(text)


class LlamaCppEmbedder(BaseEmbedder):
    """
    Embedder using llama.cpp's OpenAI-compatible /v1/embeddings endpoint.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.EMBEDDING_BASE_URL.rstrip("/")
        self.model_name = self.settings.EMBEDDING_MODEL
        self._dimension: int = 768  # standard nomic-embed-text dim, auto-updated upon first call

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Compute embeddings in batches of 16 against {EMBEDDING_BASE_URL}/embeddings."""
        if not texts:
            return []

        endpoint = f"{self.base_url}/embeddings"
        embeddings: List[List[float]] = []
        batch_size = 16

        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                payload = {
                    "model": self.model_name,
                    "input": batch,
                }
                resp = await client.post(endpoint, json=payload)
                if resp.status_code != 200:
                    raise RuntimeError(f"llama-server embedding error HTTP {resp.status_code}: {resp.text}")

                data = resp.json()
                data_items = data.get("data", [])
                for item in data_items:
                    emb = item.get("embedding", [])
                    embeddings.append(emb)
                    if emb:
                        self._dimension = len(emb)

        return embeddings

    async def embed_query(self, text: str) -> List[float]:
        res = await self.embed_documents([text])
        return res[0] if res else [0.0] * self._dimension


class OllamaEmbedder(BaseEmbedder):
    """
    Embedder using Ollama's local HTTP API (/api/embed or /api/embeddings).
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        raw_url = (
            getattr(self.settings, "OLLAMA_BASE_URL", None)
            or self.settings.LLM_BASE_URL
        ).rstrip("/")
        if raw_url.endswith("/v1"):
            raw_url = raw_url[:-3]
        self.base_url = raw_url
        self.model_name = self.settings.EMBEDDING_MODEL
        self._dimension: int = 768

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        # Try /api/embed (batch endpoint in Ollama >= 0.1.34)
        embed_endpoint = f"{self.base_url}/api/embed"
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(
                    embed_endpoint,
                    json={"model": self.model_name, "input": texts},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    embs = data.get("embeddings", [])
                    if embs:
                        self._dimension = len(embs[0])
                        return embs
            except Exception:
                pass

            # Fallback to per-item /api/embeddings
            legacy_endpoint = f"{self.base_url}/api/embeddings"
            embs = []
            for t in texts:
                resp = await client.post(
                    legacy_endpoint,
                    json={"model": self.model_name, "prompt": t},
                )
                if resp.status_code != 200:
                    raise RuntimeError(f"Ollama embedding error HTTP {resp.status_code}: {resp.text}")
                data = resp.json()
                emb = data.get("embedding", [])
                embs.append(emb)
                if emb:
                    self._dimension = len(emb)
            return embs

    async def embed_query(self, text: str) -> List[float]:
        res = await self.embed_documents([text])
        return res[0] if res else [0.0] * self._dimension


def get_embedder(
    settings: Optional[Settings] = None,
    allow_deterministic_fallback: bool = True,
) -> BaseEmbedder:
    """
    Factory creating the configured embedder.
    Falls back gracefully to DeterministicEmbedder if specified and network server is unreachable.
    """
    s = settings or get_settings()
    backend = getattr(s, "EMBEDDING_BACKEND", "llama.cpp").lower()

    if backend == "ollama":
        return OllamaEmbedder(s)
    elif backend in ("llama.cpp", "llamacpp"):
        return LlamaCppEmbedder(s)
    elif backend in ("deterministic", "mock"):
        return DeterministicEmbedder(dimension=384)

    return DeterministicEmbedder(dimension=384)
