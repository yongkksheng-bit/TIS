"""Embedding service for RAG pipeline."""
from typing import Protocol, runtime_checkable

import os


@runtime_checkable
class BaseEmbedder(Protocol):
    """Protocol for text embedding services."""

    def embed_text(self, text: str) -> list[float]:
        """Get embedding vector for a single text. Returns 1536-dim vector."""
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Get embedding vectors for multiple texts. Returns list of 1536-dim vectors."""
        ...


import hashlib
import random


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
        # Use text hash as seed for determinism
        text_hash = hashlib.md5(text.encode('utf-8')).digest()
        seed_val = int.from_bytes(text_hash[:4], 'big') / (2**32)

        # Generate deterministic pseudo-random floats from seed
        rng = random.Random(seed_val + self.seed)
        return [rng.uniform(-1.0, 1.0) for _ in range(self.DIMENSION)]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]


class DeepSeekEmbedder(BaseEmbedder):
    """
    Real DeepSeek embedding API client. NEVER instantiated in tests.
    Controlled by USE_MOCK_LLM environment variable via factory.
    """

    DIMENSION = 1536

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.base_url = "https://api.deepseek.com"

    def embed_text(self, text: str) -> list[float]:
        # Real HTTP call to DeepSeek embedding API
        # This should raise an error if USE_MOCK_LLM is not set
        raise NotImplementedError("Real API call - set USE_MOCK_LLM=True for tests")

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("Real API call - set USE_MOCK_LLM=True for tests")


def create_embedder() -> BaseEmbedder:
    """
    Factory: returns MockEmbedder when USE_MOCK_LLM=true, else DeepSeekEmbedder.
    Set env var USE_MOCK_LLM=true for testing.
    """
    if os.environ.get("USE_MOCK_LLM", "true").lower() == "true":
        return MockEmbedder()
    return DeepSeekEmbedder()
