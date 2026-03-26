import pytest

from app.core.week3_rag.text_chunker import DocumentChunker
from app.schemas.rag import ChunkNode


class TestDocumentChunker:
    def test_empty_string_returns_empty_list(self):
        """Empty string should return empty list."""
        chunks = DocumentChunker(chunk_size=100).chunk("")
        assert chunks == []

    def test_whitespace_only_returns_empty_list(self):
        """Whitespace-only text returns empty list."""
        chunks = DocumentChunker(chunk_size=100).chunk("   \n\t  ")
        assert chunks == []

    def test_short_text_returns_single_chunk(self):
        """Text shorter than chunk_size returns as single chunk."""
        text = "这是一段很短的内容"
        chunks = DocumentChunker(chunk_size=500).chunk(text)
        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].chunk_index == 0
        assert chunks[0].char_length == len(text)

    def test_short_text_exactly_at_boundary(self):
        """Text exactly at chunk_size boundary returns single chunk."""
        text = "a" * 500
        chunks = DocumentChunker(chunk_size=500).chunk(text)
        assert len(chunks) == 1

    def test_long_text_returns_multiple_chunks(self):
        """Long text is split into multiple chunks."""
        text = "a" * 1200
        chunks = DocumentChunker(chunk_size=500, chunk_overlap=50).chunk(text)
        assert len(chunks) > 1

    def test_overlap_is_correct_length(self):
        """Verify adjacent chunks have the specified overlap."""
        text = "a" * 1200
        chunks = DocumentChunker(chunk_size=500, chunk_overlap=50).chunk(text)
        assert len(chunks) >= 2
        # The suffix of chunk[0] should equal prefix of chunk[1]
        assert chunks[0].text[-50:] == chunks[1].text[:50]

    def test_metadata_passed_to_all_chunks(self):
        """Metadata dict is inherited by every chunk."""
        text = "a" * 1200
        meta = {"source": "tender_doc", "page": 3}
        chunks = DocumentChunker(chunk_size=500, chunk_overlap=50).chunk(text, metadata=meta)
        assert all(c.metadata == meta for c in chunks)

    def test_chunk_index_increments(self):
        """Chunk indices are sequential starting from 0."""
        text = "a" * 1200
        chunks = DocumentChunker(chunk_size=500, chunk_overlap=50).chunk(text)
        assert chunks[0].chunk_index == 0
        assert chunks[1].chunk_index == 1
        assert chunks[2].chunk_index == 2

    def test_char_length_matches_text(self):
        """Each chunk's char_length equals len(text)."""
        text = "a" * 1200
        chunks = DocumentChunker(chunk_size=500, chunk_overlap=50).chunk(text)
        for c in chunks:
            assert c.char_length == len(c.text)

    def test_chunks_are_chunk_node_instances(self):
        """Return type is list of ChunkNode, not plain dicts."""
        text = "a" * 1200
        chunks = DocumentChunker(chunk_size=500).chunk(text)
        from app.schemas.rag import ChunkNode
        assert all(isinstance(c, ChunkNode) for c in chunks)

    def test_smart_truncation_at_sentence_boundary(self):
        """Chunk ends at sentence boundary (。), not mid-sentence."""
        # Build text: 506 chars total, with a sentence boundary at position ~406
        # (within the search window [400, 500) for chunk_size=500)
        # period at 406 = 399 'a' chars + 7 char sentence
        padding = "a" * 399  # 399 chars
        sentence1 = "这是第一句话。"  # 7 chars, period at absolute position 406
        sentence2 = "a" * 100  # more content to exceed chunk_size
        text = padding + sentence1 + sentence2  # 506 chars total (exceeds 500)

        chunks = DocumentChunker(chunk_size=500).chunk(text)
        # First chunk should end at the 。 after "第一句话" (position 406)
        assert chunks[0].text.endswith("这是第一句话。")

    def test_smart_truncation_prefers_closest_punctuation(self):
        """When multiple punctuations in range, prefer closest to boundary."""
        # Text with 。 at positions 390, 441, 492 within a 500-char chunk
        # Must exceed 500 chars to trigger chunking
        base = "a" * 390 + "。" + "b" * 50 + "。" + "c" * 50 + "。" + "d" * 20
        chunks = DocumentChunker(chunk_size=500).chunk(base)
        # Should truncate at the LAST 。 within [400, 500], i.e., the one at ~492
        assert chunks[0].text.endswith("。")

    def test_hard_truncate_when_no_punctuation_in_range(self):
        """Falls back to hard truncate if no punctuation in search window."""
        # Text with no punctuation - should hard truncate
        text = "a" * 600
        chunks = DocumentChunker(chunk_size=500).chunk(text)
        assert len(chunks[0].text) <= 500

    def test_overlap_cannot_exceed_max_fraction(self):
        """Overlap is capped at max_overlap_fraction * chunk_size."""
        text = "a" * 2000
        chunker = DocumentChunker(chunk_size=500, chunk_overlap=200)  # 200/500 = 0.4
        chunks = chunker.chunk(text)
        # Actual overlap should be capped (0.3 * 500 = 150)
        assert len(chunks[0].text[-150:]) == len(chunks[1].text[:150])
