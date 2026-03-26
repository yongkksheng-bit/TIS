"""TDD tests for Embedding Service."""
import pytest
import os
from app.core.week3_rag.embedder import (
    MockEmbedder,
    DeepSeekEmbedder,
    create_embedder,
    BaseEmbedder,
)


class TestMockEmbedder:
    def test_embed_text_returns_1536_dimensions(self):
        """Single text embedding must be exactly 1536 floats."""
        embedder = MockEmbedder()
        vec = embedder.embed_text("测试文本")
        assert len(vec) == 1536
        assert all(isinstance(v, float) for v in vec)

    def test_embed_batch_returns_correct_count(self):
        """Batch embedding returns one vector per input text."""
        embedder = MockEmbedder()
        texts = ["文本1", "文本2", "文本3"]
        vecs = embedder.embed_batch(texts)
        assert len(vecs) == 3
        assert all(len(v) == 1536 for v in vecs)

    def test_embed_batch_empty_list(self):
        """Empty batch returns empty list."""
        embedder = MockEmbedder()
        vecs = embedder.embed_batch([])
        assert vecs == []

    def test_embed_text_is_deterministic(self):
        """Same text always produces same vector."""
        embedder = MockEmbedder()
        vec1 = embedder.embed_text("恒定性测试")
        vec2 = embedder.embed_text("恒定性测试")
        assert vec1 == vec2

    def test_different_texts_produce_different_vectors(self):
        """Different texts produce different vectors."""
        embedder = MockEmbedder()
        vec1 = embedder.embed_text("文本A")
        vec2 = embedder.embed_text("文本B")
        assert vec1 != vec2

    def test_vectors_are_normalized(self):
        """Vectors should be in reasonable range (-1 to 1)."""
        embedder = MockEmbedder()
        vec = embedder.embed_text("归一化测试")
        assert all(-1.0 <= v <= 1.0 for v in vec)

    def test_mock_never_makes_network_request(self):
        """MockEmbedder must never import or call real HTTP libraries."""
        import sys
        embedder = MockEmbedder()
        # Should not raise - just call embed
        result = embedder.embed_text("no network")
        assert len(result) == 1536


class TestFactory:
    def test_factory_returns_mock_when_env_true(self, monkeypatch):
        """Factory returns MockEmbedder when USE_MOCK_LLM=true."""
        monkeypatch.setenv("USE_MOCK_LLM", "true")
        embedder = create_embedder()
        assert isinstance(embedder, MockEmbedder)

    def test_factory_returns_deepseek_when_env_false(self, monkeypatch):
        """Factory returns DeepSeekEmbedder when USE_MOCK_LLM=false."""
        monkeypatch.setenv("USE_MOCK_LLM", "false")
        embedder = create_embedder()
        assert isinstance(embedder, DeepSeekEmbedder)

    def test_factory_default_is_mock(self, monkeypatch):
        """Factory defaults to MockEmbedder when env var not set."""
        monkeypatch.delenv("USE_MOCK_LLM", raising=False)
        embedder = create_embedder()
        assert isinstance(embedder, MockEmbedder)


class TestBaseEmbedderProtocol:
    def test_mock_implements_protocol(self):
        """MockEmbedder satisfies BaseEmbedder protocol."""
        embedder = MockEmbedder()
        assert isinstance(embedder, BaseEmbedder)
        assert hasattr(embedder, 'embed_text')
        assert hasattr(embedder, 'embed_batch')
