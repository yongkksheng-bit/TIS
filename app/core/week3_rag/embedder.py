"""Embedding service for RAG pipeline."""
from typing import Protocol, runtime_checkable
import os
import hashlib
import random
import json
import urllib.request
import urllib.error


@runtime_checkable
class BaseEmbedder(Protocol):
    """Protocol for text embedding services."""

    def embed_text(self, text: str) -> list[float]:
        """Get embedding vector for a single text. Returns 1536-dim vector."""
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Get embedding vectors for multiple texts. Returns list of 1536-dim vectors."""
        ...


class MockEmbedder(BaseEmbedder):
    """
    Deterministic mock embedder for TDD. Returns 1536-dim float vectors.
    - All-zero vector is too easy to accidentally pass with wrong length
    - Use text content to generate a deterministic seed, then fill with pseudo-random floats
    - MUST NEVER make any network requests
    """

    DIMENSION = 1536

    def __init__(self, seed: float = 0.0):
        self.seed = seed

    def embed_text(self, text: str) -> list[float]:
        """Generate a deterministic 1536-dim vector based on text content."""
        text_hash = hashlib.md5(text.encode('utf-8')).digest()
        seed_val = int.from_bytes(text_hash[:4], 'big') / (2**32)
        rng = random.Random(seed_val + self.seed)
        return [rng.uniform(-1.0, 1.0) for _ in range(self.DIMENSION)]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]


class AIServiceEmbedder(BaseEmbedder):
    """
    Local AI microservice embedder — BGE-Small on GPU via tis_ai_service.

    Embedding/reranking MUST use this local service.
    DeepSeek API is ONLY for final LLM text generation (chat/completions).

    Service URL (Docker internal network): http://ai_service:8000/embed
    """

    DIMENSION = 512  # BGE-small-zh-v1.5 outputs 512-dim vectors
    BASE_URL = "http://ai_service:8000"

    def _call_embed_api(self, texts: list[str]) -> list[list[float]]:
        """Call local ai_service /embed endpoint."""
        url = f"{self.BASE_URL}/embed"
        payload = {"texts": texts}
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            raise RuntimeError(
                f"AIService embed API error {e.code}: {error_body}"
            ) from e
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Network error calling AIService embed: {e.reason}"
            ) from e

        embeddings = result.get("embeddings", [])
        if not embeddings:
            raise RuntimeError(f"AIService embed returned no data: {result}")
        return embeddings

    def embed_text(self, text: str) -> list[float]:
        """Get embedding vector for a single text. Returns 512-dim vector."""
        return self._call_embed_api([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Get embedding vectors for multiple texts. Returns list of 512-dim vectors."""
        return self._call_embed_api(texts)


def create_embedder() -> BaseEmbedder:
    """
    Factory: returns MockEmbedder when USE_MOCK_EMBEDDER=true,
    else AIServiceEmbedder (local BGE model).

    Set env var USE_MOCK_EMBEDDER=true for testing without ai_service.
    """
    use_mock = os.environ.get("USE_MOCK_EMBEDDER", "true").lower() == "true"
    if use_mock:
        return MockEmbedder()
    return AIServiceEmbedder()
