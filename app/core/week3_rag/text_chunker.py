from typing import Any

from app.schemas.rag import ChunkNode


class DocumentChunker:
    """
    Splits large text into overlapping semantic chunks for RAG.

    Parameters:
        chunk_size: max characters per chunk (default 500)
        chunk_overlap: overlap between adjacent chunks (default 50)
        max_overlap_fraction: max overlap as fraction of chunk_size (default 0.3)

    Smart truncation:
    - When hitting chunk_size limit, search backward for nearest sentence-ending
      punctuation (，。！？.!?\\n) within last 20% of chunk
    - If found, truncate at that punctuation + skip the punctuation itself
    - Fall back to hard truncate if no punctuation found within window
    """

    # Sentence-ending punctuation in priority order (prefer natural boundaries)
    SENTENCE_PUNCTUATIONS = ["\n", "。", "！", "？", ".", "!", "?"]

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        max_overlap_fraction: float = 0.3,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_overlap_fraction = max_overlap_fraction

    def _find_sentence_boundary(self, text: str, start: int, end: int) -> int | None:
        """
        Find the best sentence boundary within [chunk_size * 0.8, chunk_size] range.

        Returns the index AFTER the punctuation (where we should truncate),
        or None if no boundary found.
        """
        chunk_start = start
        chunk_end = end
        chunk_len = chunk_end - chunk_start

        # Search window: last 20% of chunk
        search_start = max(chunk_start + int(chunk_len * 0.8), start)
        search_window = text[search_start:chunk_end]

        # Search for punctuation in priority order, finding the LAST occurrence
        best_pos = None

        for punct in self.SENTENCE_PUNCTUATIONS:
            pos = search_window.rfind(punct)
            if pos != -1:
                # pos is relative to search_window, convert to absolute position
                abs_pos = search_start + pos
                # We want to cut AFTER the punctuation
                boundary_pos = abs_pos + 1
                # Make sure it's within the chunk
                if boundary_pos <= chunk_end:
                    if best_pos is None or boundary_pos > best_pos:
                        best_pos = boundary_pos

        return best_pos

    def chunk(self, text: str, metadata: dict[str, Any] | None = None) -> list[ChunkNode]:
        """
        Split text into overlapping chunks with smart truncation.

        Args:
            text: input text to chunk
            metadata: optional dict of metadata to attach to every chunk

        Returns:
            list of ChunkNode objects (never dicts)
        """
        if metadata is None:
            metadata = {}

        # Handle empty or whitespace-only text
        if not text or text.isspace():
            return []

        # Short text - return as single chunk
        if len(text) <= self.chunk_size:
            return [
                ChunkNode(
                    text=text,
                    chunk_index=0,
                    char_length=len(text),
                    metadata=metadata,
                )
            ]

        # Calculate effective overlap (capped at max_overlap_fraction)
        effective_overlap = min(
            self.chunk_overlap,
            int(self.chunk_size * self.max_overlap_fraction)
        )

        chunks = []
        chunk_index = 0
        current_pos = 0
        text_len = len(text)

        while current_pos < text_len:
            # Calculate end position for this chunk
            chunk_end = min(current_pos + self.chunk_size, text_len)

            # If we're not at the end of the text, try smart truncation
            if chunk_end < text_len:
                # Try to find a sentence boundary
                boundary = self._find_sentence_boundary(text, current_pos, chunk_end)
                if boundary is not None:
                    chunk_end = boundary

            # Extract the chunk
            chunk_text = text[current_pos:chunk_end]

            # Create ChunkNode
            chunks.append(
                ChunkNode(
                    text=chunk_text,
                    chunk_index=chunk_index,
                    char_length=len(chunk_text),
                    metadata=metadata,
                )
            )

            chunk_index += 1

            # Move position back by overlap for next chunk
            # If we hit the end of text, break
            if chunk_end >= text_len:
                break

            # Calculate next start position (backtrack by overlap)
            next_pos = chunk_end - effective_overlap

            # Ensure we make progress
            if next_pos <= current_pos:
                next_pos = current_pos + 1

            current_pos = next_pos

        return chunks


# ─── HistoricalChunker: scoring-dimension-aware sliding window ────────────────


class HistoricalChunker:
    """
    Splits historical tender/expert feedback documents by scoring dimensions
    using a sliding window, so each chunk aligns to a specific evaluation
    sub-criterion (e.g. "食材溯源", "冷链管理").

    This class is ENTIRELY independent of DocumentChunker — no shared state.

    Parameters:
        chunk_size: max characters per chunk (default 600, slightly larger for expert text)
        chunk_overlap: overlap between adjacent chunks (default 80)
        max_overlap_fraction: max overlap as fraction of chunk_size (default 0.3)
    """

    SENTENCE_PUNCTUATIONS = ["\n", "。", "！", "？", ".", "!", "?"]

    def __init__(
        self,
        chunk_size: int = 600,
        chunk_overlap: int = 80,
        max_overlap_fraction: float = 0.3,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_overlap_fraction = max_overlap_fraction

    def chunk_by_dimensions(
        self,
        text: str,
        dimension_names: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> list[ChunkNode]:
        """
        Split text into chunks aligned to scoring dimensions.

        For each dimension name found in the text, extracts the text between
        that dimension header and the next one, then applies sliding-window
        chunking to each segment independently.

        Args:
            text: full expert feedback or tender scoring criteria text
            dimension_names: list of dimension sub-item names to look for
                              (e.g. ["食材溯源", "冷链管理", "卫生保障"])
            metadata: optional base metadata dict to attach to every chunk

        Returns:
            list of ChunkNode objects, one per dimension-aware chunk
        """
        if metadata is None:
            metadata = {}

        if not text or text.isspace():
            return []

        # Split text into dimension segments
        segments = self._split_by_dimensions(text, dimension_names)

        if not segments:
            # Fallback: treat entire text as single segment
            return self._sliding_window(text, metadata, 0)

        all_chunks: list[ChunkNode] = []
        chunk_index = 0

        for dim_name, segment_text in segments:
            dim_meta = {**metadata, "scoring_dimension_tags": [dim_name]}
            chunks = self._sliding_window(segment_text, dim_meta, chunk_index)
            all_chunks.extend(chunks)
            chunk_index += len(chunks)

        return all_chunks

    def _split_by_dimensions(
        self,
        text: str,
        dimension_names: list[str],
    ) -> list[tuple[str, str]]:
        """
        Find each dimension occurrence in text and extract its content.

        Returns list of (dimension_name, content_between_this_and_next_dimension).
        If no dimensions found, returns empty list.
        """
        occurrences: list[tuple[int, str]] = []

        for dim in dimension_names:
            start = 0
            while True:
                pos = text.find(dim, start)
                if pos == -1:
                    break
                # Only accept at word boundary (preceded by newline, space, colon, or start)
                if pos == 0 or text[pos - 1] in "\n\r\t （(":
                    occurrences.append((pos, dim))
                start = pos + len(dim)

        if not occurrences:
            return []

        # Sort by position
        occurrences.sort(key=lambda x: x[0])

        # Extract content between consecutive occurrences
        segments: list[tuple[str, str]] = []
        for i, (pos, dim) in enumerate(occurrences):
            seg_start = pos + len(dim)
            seg_end = occurrences[i + 1][0] if i + 1 < len(occurrences) else len(text)
            content = text[seg_start:seg_end].strip()
            if content:
                segments.append((dim, content))

        return segments

    def _sliding_window(
        self,
        text: str,
        metadata: dict[str, Any],
        start_index: int,
    ) -> list[ChunkNode]:
        """Apply sliding-window chunking to a single text segment."""
        if not text or text.isspace():
            return []

        if len(text) <= self.chunk_size:
            return [
                ChunkNode(
                    text=text,
                    chunk_index=start_index,
                    char_length=len(text),
                    metadata=metadata,
                )
            ]

        effective_overlap = min(
            self.chunk_overlap,
            int(self.chunk_size * self.max_overlap_fraction),
        )

        chunks: list[ChunkNode] = []
        chunk_index = start_index
        current_pos = 0
        text_len = len(text)

        while current_pos < text_len:
            chunk_end = min(current_pos + self.chunk_size, text_len)

            if chunk_end < text_len:
                boundary = self._find_sentence_boundary(text, current_pos, chunk_end)
                if boundary is not None:
                    chunk_end = boundary

            chunk_text = text[current_pos:chunk_end]
            chunks.append(
                ChunkNode(
                    text=chunk_text,
                    chunk_index=chunk_index,
                    char_length=len(chunk_text),
                    metadata=metadata,
                )
            )

            chunk_index += 1

            if chunk_end >= text_len:
                break

            next_pos = chunk_end - effective_overlap
            if next_pos <= current_pos:
                next_pos = current_pos + 1
            current_pos = next_pos

        return chunks

    def _find_sentence_boundary(self, text: str, start: int, end: int) -> int | None:
        """Find best sentence boundary within the last 20% of the chunk window."""
        chunk_len = end - start
        search_start = max(start + int(chunk_len * 0.8), start)
        search_window = text[search_start:end]

        best_pos = None
        for punct in self.SENTENCE_PUNCTUATIONS:
            pos = search_window.rfind(punct)
            if pos != -1:
                abs_pos = search_start + pos
                boundary_pos = abs_pos + 1
                if boundary_pos <= end:
                    if best_pos is None or boundary_pos > best_pos:
                        best_pos = boundary_pos

        return best_pos
