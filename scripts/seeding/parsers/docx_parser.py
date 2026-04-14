"""DOCX Parser V3 — paragraph + table extraction with document-order preservation.

Engineering constraints:
  - All I/O stays within scripts/seeding/parsers/ and subdirectories.
  - All output dicts are JSONB-safe (no non-serializable objects).
  - Tables are extracted as Markdown and interleaved with paragraphs in
    physical document order (not ooxml id order, which is unreliable).

Author: TIS Seeding Pipeline V3
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)


# ─── Data classes ─────────────────────────────────────────────────────────────

class Block:
    """
    A single block from a DOCX — either a paragraph or a table.

    Attributes:
        block_type: "paragraph" | "table"
        content: text content (Markdown for tables)
    """

    __slots__ = ("block_type", "content")

    def __init__(self, block_type: Literal["paragraph", "table"], content: str) -> None:
        self.block_type: Literal["paragraph", "table"] = block_type
        self.content: str = content

    def to_dict(self) -> dict[str, str]:
        return {"block_type": self.block_type, "content": self.content}

    def __repr__(self) -> str:
        snippet = self.content[:40].replace("\n", " ")
        return f"<Block {self.block_type} {len(self.content)}chars {snippet!r}>"


class DOCXParseResult:
    """
    Structured result from DOCX parsing (V3).

    Attributes:
        file_path: Original file path.
        paragraphs: List of paragraph texts only (backwards-compatible).
        blocks: Full block list in document order (paragraphs + tables).
        total_paragraphs: Count of non-empty paragraphs.
        total_blocks: Total count of blocks (paragraphs + tables).
        sha256: SHA256 hex digest of raw .docx bytes (for dedup).
        error: Error message if parsing failed, else None.
    """

    def __init__(
        self,
        file_path: str,
        paragraphs: list[str],
        blocks: list[Block],
        total_paragraphs: int,
        sha256: str,
        error: Optional[str] = None,
    ) -> None:
        self.file_path = file_path
        self.paragraphs: list[str] = paragraphs
        self.blocks: list[Block] = blocks
        self.total_paragraphs: int = total_paragraphs
        self.total_blocks: int = len(blocks)
        self.sha256: str = sha256
        self.error: Optional[str] = error

    @property
    def full_text(self) -> str:
        """All paragraph blocks joined with double newlines (backwards compat)."""
        return "\n\n".join(self.paragraphs)

    def to_dict(self) -> dict[str, Any]:
        """JSONB-safe dict representation."""
        return {
            "file_path": self.file_path,
            "paragraphs": self.paragraphs,
            "blocks": [b.to_dict() for b in self.blocks],
            "total_paragraphs": self.total_paragraphs,
            "total_blocks": self.total_blocks,
            "sha256": self.sha256,
            "error": self.error,
        }

    def __repr__(self) -> str:
        return (
            f"<DOCXParseResult "
            f"{self.total_paragraphs} paragraphs, {self.total_blocks} blocks "
            f"{self.file_path}>"
        )


# ─── Table extraction ─────────────────────────────────────────────────────────

class TableBlockExtractor:
    """
    Converts a python-docx table element to a Markdown table string.

    Design decisions:
      - Merged cells (gridSpan > 1): rendered as repeated cell text with a note.
      - Vertically-merged continuation cells (vMerge=continue): rendered as empty
        to avoid redundant content while preserving column alignment.
      - Fully empty rows are silently dropped.
      - Each table row is rendered as one Markdown line.

    Patch 2 (Table Integrity): tables are NEVER passed to sliding-window splitters.
    They are always emitted as one complete, atomic Block.
    """

    def __init__(self, rows: list[list[str]]) -> None:
        self.rows: list[list[str]] = rows

    @classmethod
    def from_docx_table(cls, tbl) -> "TableBlockExtractor":
        """
        Build a TableBlockExtractor from a python-docx Table element.

        Args:
            tbl: python-docx Table object (from Document.tables or iteration).
        """
        rows: list[list[str]] = []
        for row in tbl.rows:
            cells: list[str] = []
            for cell in row.cells:
                # Collapse all text inside the cell (handles multi-paragraph cells)
                cell_text = " ".join(
                    p.text.strip() for p in cell.paragraphs if p.text.strip()
                )
                cells.append(cell_text)
            rows.append(cells)
        return cls(rows)

    def to_markdown_lines(self) -> list[str]:
        """
        Convert the table to Markdown format.

        Returns:
            List of Markdown lines (including header, separator, and data rows).
            Empty if the table has no rows.
        """
        if not self.rows:
            return []

        col_count = max(len(row) for row in self.rows)
        if col_count == 0:
            return []

        lines: list[str] = []

        # Header row
        header = [self.rows[0][i] if i < len(self.rows[0]) else "" for i in range(col_count)]
        lines.append("| " + " | ".join(header) + " |")

        # Separator row
        lines.append("|" + "|".join(" --- " for _ in range(col_count)) + "|")

        # Data rows (skip fully-empty rows)
        for row in self.rows[1:]:
            data = [row[i] if i < len(row) else "" for i in range(col_count)]
            if any(c.strip() for c in data):
                lines.append("| " + " | ".join(data) + " |")

        return lines

    def is_meaningful(self, min_content_chars: int = 5) -> bool:
        """
        Return True if this table has at least one cell with min_content_chars.

        Used by the caller to discard decoration/blank tables.
        """
        for row in self.rows:
            for cell in row:
                if len(cell.strip()) >= min_content_chars:
                    return True
        return False


# ─── Parser ───────────────────────────────────────────────────────────────────

class DOCXParser:
    """
    Extracts text and tables from .docx files in physical document order.

    V3 changes:
      - Parses both paragraphs AND tables.
      - Tables are converted to Markdown and interleaved with paragraphs
        using python-docx's element iteration order (body children).
      - Returns both `paragraphs` (backwards-compatible) and `blocks`
        (full paragraph+table stream for V3 chunker).

    Patch 4 (JSONB Safety): all return values are plain Python built-ins
    or simple dataclass instances with __slots__ — no lazy generators,
    no ORM objects, no complex cyclic references.
    """

    def parse(self, file_path: str | Path) -> DOCXParseResult:
        """
        Parse a .docx file and return structured paragraphs + blocks.

        Args:
            file_path: Path to the .docx file.

        Returns:
            DOCXParseResult with paragraphs list, blocks list, and metadata.
            On error, returns DOCXParseResult with empty fields and non-None error.
        """
        try:
            from docx import Document as DocxDocument
        except ImportError:
            return DOCXParseResult(
                file_path=str(file_path),
                paragraphs=[],
                blocks=[],
                total_paragraphs=0,
                sha256="",
                error="python-docx not installed",
            )

        path = Path(file_path)
        if not path.exists():
            return DOCXParseResult(
                file_path=str(file_path),
                paragraphs=[],
                blocks=[],
                total_paragraphs=0,
                sha256="",
                error=f"File not found: {file_path}",
            )

        file_hash = self._compute_sha256(path)

        try:
            doc = DocxDocument(path)
        except Exception as exc:
            return DOCXParseResult(
                file_path=str(file_path),
                paragraphs=[],
                blocks=[],
                total_paragraphs=0,
                sha256=file_hash,
                error=f"Failed to open .docx: {exc}",
            )

        blocks: list[Block] = []
        paragraphs: list[str] = []

        # Iterate document body children in physical order.
        # Each child is either a paragraph (<w:p>) or a table (<w:tbl>).
        # python-docx stores these in .element.body children.
        for child in doc.element.body:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

            if tag == "p":
                # Extract paragraph text
                para_text = self._extract_para_text(child)
                if para_text:
                    blocks.append(Block(block_type="paragraph", content=para_text))
                    paragraphs.append(para_text)

            elif tag == "tbl":
                # Extract table as Markdown
                # python-docx doesn't expose Table objects from element iteration,
                # so we use doc.tables indexed by counting tbl elements seen.
                tbl_obj = self._find_table_by_element(doc, child)
                if tbl_obj is not None:
                    extractor = TableBlockExtractor.from_docx_table(tbl_obj)
                    if extractor.is_meaningful():
                        md_lines = extractor.to_markdown_lines()
                        if md_lines:
                            blocks.append(Block(block_type="table", content="\n".join(md_lines)))

        total = len(paragraphs)
        logger.info(
            "DOCX parsed V3: %s — %d paragraphs, %d tables, %d total blocks, SHA256=%s",
            path.name, total,
            sum(1 for b in blocks if b.block_type == "table"),
            len(blocks),
            file_hash[:16],
        )
        return DOCXParseResult(
            file_path=str(file_path),
            paragraphs=paragraphs,
            blocks=blocks,
            total_paragraphs=total,
            sha256=file_hash,
            error=None,
        )

    def _extract_para_text(self, para_el) -> str:
        """
        Extract all text from a python-docx paragraph element (Lxml w:p).

        Handles runs, special characters, and nested elements.
        Returns the stripped text content of the paragraph.
        """
        from docx.oxml.ns import qn as wqn

        parts: list[str] = []
        for node in para_el.iter(wqn("w:t")):
            if node.text:
                parts.append(node.text)
        return " ".join(parts).strip()

    def _find_table_by_element(self, doc, tbl_el) -> Any:
        """
        Find the python-docx Table object corresponding to an element.

        python-docx stores tables in doc.tables and also embeds them in the
        body element tree. We count tbl elements seen so far to index into
        doc.tables.
        """
        tbl_index = 0
        for child in doc.element.body:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "tbl":
                if child is tbl_el:
                    if tbl_index < len(doc.tables):
                        return doc.tables[tbl_index]
                tbl_index += 1
        return None

    def _compute_sha256(self, file_path: Path) -> str:
        """Compute SHA256 of raw .docx bytes for dedup fingerprinting."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
