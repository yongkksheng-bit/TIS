"""PDF Parser using pdfplumber — with aggressive downsampling for large files.

Design:
  - Uses pdfplumber for text extraction (pure Python, no system deps).
  - >max_pages triggers smart downsampling (not blind truncation).
  - Large-file strategy: first 10 pages + last 5 pages + keyword-hit middle pages.
  - pdfplumber is used as an iterator — never loads full PDF into memory.
  - SHA256 computed on raw bytes for dedup fingerprinting.

Error handling:
  - Corrupt PDF → PDFParseResult with non-None error, empty pages.
  - Password-protected → PDFParseResult with non-None error.
  - Empty page (no text) → page is skipped (not included).

Author: TIS Seeding Pipeline
"""
from __future__ import annotations

import hashlib
import io
import logging
import warnings
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy import — pdfplumber is not a core dependency; install via:
#   pip install pdfplumber
# We catch ImportError and degrade gracefully.
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False


# ─── Custom exceptions ─────────────────────────────────────────────────────────

class PDFParseError(Exception):
    """Base exception for PDF parsing failures."""
    pass


class PDFEncryptedError(PDFParseError):
    """Raised when the PDF is password-protected / encrypted."""
    pass


class PDFCorruptError(PDFParseError):
    """Raised when the PDF structure is corrupt or unreadable."""
    pass


# ─── Parse result dataclass ───────────────────────────────────────────────────

class PDFParseResult:
    """
    Structured result from PDF parsing.

    Attributes:
        file_path: Original file path (for dedup fingerprinting).
        pages: List of non-empty page texts, in order. Empty list on failure.
        total_pages: Total page count in the original PDF.
        is_downsampled: True if the file was downsampled (> max_pages).
        page_count: Number of pages actually extracted (after downsampling).
        sha256: SHA256 hex of raw PDF bytes.
        error: Error message if parsing failed, else None.
    """

    def __init__(
        self,
        file_path: str,
        pages: list[str],
        total_pages: int,
        is_downsampled: bool,
        sha256: str,
        error: Optional[str] = None,
    ):
        self.file_path = file_path
        self.pages = pages
        self.total_pages = total_pages
        self.is_downsampled = is_downsampled
        self.page_count = len(pages)
        self.sha256 = sha256
        self.error = error

    @property
    def full_text(self) -> str:
        """All page texts joined into one string."""
        return "\n\n".join(self.pages)

    def __repr__(self) -> str:
        status = "DOWNSAMPLED" if self.is_downsampled else "FULL"
        return (
            f"<PDFParseResult {self.page_count}/{self.total_pages} pages "
            f"[{status}] {Path(self.file_path).name}>"
        )


# ─── Core parser ───────────────────────────────────────────────────────────────

class PDFParser:
    """
    Extracts text from PDF files with memory-conscious smart downsampling.

    Downsampling strategy (>max_pages):
      1. ALWAYS extract first 10 pages  — tender notice, table of contents, metadata.
      2. ALWAYS extract last 5 pages    — annexes, bid forms, signature pages.
      3. MIDDLE pages: scan each page text; extract it only if it contains
         at least one SCORING_KEYWORD. Collect at most KEYWORD_HIT_PAGES_LIMIT
         middle pages (oldest-first) to bound memory use.

    Memory guarantee: pdfplumber PDF.open() returns an iterable;
    pages are processed one at a time, never the full PDF in memory.

    Attributes:
        max_pages: Threshold for triggering downsampling (default 100).
        front_pages: Number of front pages to always extract (default 10).
        back_pages: Number of back pages to always extract (default 5).
        keyword_hit_limit: Max middle pages to extract (default 10).
    """

    SCORING_KEYWORDS = [
        # Scoring-dimension keywords
        "评分", "评标", "评分标准", "评标标准", "评分细则", "评标办法",
        "技术评分", "商务评分", "综合评分", "价格评分", "权重",
        "扣分", "得分", "技术分", "商务分", "报价分",
        # Business content keywords
        "服务方案", "技术方案", "配送方案", "实施方案",
        "技术要求", "服务要求", "质量要求", "规格要求",
        "报价", "投标报价", "总价", "预算金额",
        "资质", "业绩", "成功案例", "企业业绩",
        "卫生", "食品安全", "冷链", "溯源",
    ]

    def __init__(
        self,
        max_pages: int = 100,
        front_pages: int = 10,
        back_pages: int = 5,
        keyword_hit_limit: int = 10,
    ):
        self.max_pages = max_pages
        self.front_pages = front_pages
        self.back_pages = back_pages
        self.keyword_hit_limit = keyword_hit_limit

    def parse(self, file_path: str | Path) -> PDFParseResult:
        """
        Parse a PDF file and return structured text pages.

        Args:
            file_path: Path to the PDF file.

        Returns:
            PDFParseResult with list of page texts and metadata.
            On error (corrupt, encrypted, missing), returns
            PDFParseResult with empty pages and non-None error.
        """
        path = Path(file_path)
        if not path.exists():
            return PDFParseResult(
                file_path=str(path),
                pages=[],
                total_pages=0,
                is_downsampled=False,
                sha256="",
                error=f"File not found: {path}",
            )

        if not PDFPLUMBER_AVAILABLE:
            return PDFParseResult(
                file_path=str(path),
                pages=[],
                total_pages=0,
                is_downsampled=False,
                sha256=self._compute_sha256(path),
                error="pdfplumber not installed — run: pip install pdfplumber",
            )

        # ── Compute SHA256 first (dedup fingerprint — done even if parse fails) ──
        sha256_hex = self._compute_sha256(path)

        try:
            pages_text, total = self._extract_pages(path)
        except PDFEncryptedError as exc:
            logger.error("PDF is encrypted: %s — %s", path, exc)
            return PDFParseResult(
                file_path=str(path),
                pages=[],
                total_pages=0,
                is_downsampled=False,
                sha256=sha256_hex,
                error=f"PDF encrypted: {exc}",
            )
        except PDFCorruptError as exc:
            logger.error("PDF is corrupt: %s — %s", path, exc)
            return PDFParseResult(
                file_path=str(path),
                pages=[],
                total_pages=0,
                is_downsampled=False,
                sha256=sha256_hex,
                error=f"PDF corrupt or unreadable: {exc}",
            )
        except Exception as exc:
            # Catch-all: any other PDF reading error
            logger.error("PDF read error: %s — %s", path, exc)
            return PDFParseResult(
                file_path=str(path),
                pages=[],
                total_pages=0,
                is_downsampled=False,
                sha256=sha256_hex,
                error=f"PDF read error: {type(exc).__name__}: {exc}",
            )

        # ── Downsampling decision ────────────────────────────────────────────
        is_downsampled = total > self.max_pages
        if is_downsampled:
            pages_text = self._downsample(path, pages_text, total)
            logger.warning(
                "DOWNSAMPLED: %s — extracted %d/%d pages (threshold=%d). "
                "Strategy: first %d + last %d + keyword-hit middle pages.",
                path.name, len(pages_text), total, self.max_pages,
                self.front_pages, self.back_pages,
            )

        return PDFParseResult(
            file_path=str(path),
            pages=pages_text,
            total_pages=total,
            is_downsampled=is_downsampled,
            sha256=sha256_hex,
        )

    def _extract_pages(self, path: Path) -> tuple[list[str], int]:
        """
        Extract all non-empty page texts from a PDF using pdfplumber.

        Returns:
            (list of page texts, total_page_count)

        Raises:
            PDFEncryptedError: if PDF requires a password.
            PDFCorruptError: if PDF structure is invalid.
        """
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=Warning)
                with pdfplumber.open(path) as pdf:
                    total = len(pdf.pages)

                    # Check for encryption
                    if pdf.is_encrypted:
                        raise PDFEncryptedError(f"PDF is encrypted: {path.name}")

                    pages: list[str] = []
                    for page in pdf.pages:
                        try:
                            text = page.extract_text() or ""
                        except Exception as exc:
                            logger.debug("Could not extract text from page: %s", exc)
                            text = ""

                        text = text.strip()
                        if text:
                            pages.append(text)

                    return pages, total

        except PDFEncryptedError:
            raise
        except Exception as exc:
            if "password" in str(exc).lower() or "encrypted" in str(exc).lower():
                raise PDFEncryptedError(str(exc)) from exc
            raise PDFCorruptError(str(exc)) from exc

    def _downsample(
        self,
        path: Path,
        all_pages: list[str],
        total: int,
    ) -> list[str]:
        """
        Apply smart downsampling to keep page count within max_pages.

        Rules:
          - First 10 pages (index 0..9): always keep
          - Last 5 pages (index N-5..N-1): always keep
          - Middle pages (index 10..N-6): keep ONLY if they contain
            at least one SCORING_KEYWORD; collect at most keyword_hit_limit
            of these (oldest-first).

        Args:
            path: Original file path (for warning message context).
            all_pages: List of ALL page texts (already filtered to non-empty).
            total: Total page count from pdfplumber.

        Returns:
            List of selected page texts (non-empty, in original order).
        """
        n = total
        keep_indices: set[int] = set()

        # 1. Always keep first `front_pages` pages
        for i in range(min(self.front_pages, n)):
            keep_indices.add(i)

        # 2. Always keep last `back_pages` pages
        for i in range(max(0, n - self.back_pages), n):
            keep_indices.add(i)

        # 3. Middle pages: scan for scoring keywords (up to keyword_hit_limit)
        keyword_hit_pages: list[int] = []
        for i in range(self.front_pages, n - self.back_pages):
            if self._is_keyword_page(all_pages[i]):
                keyword_hit_pages.append(i)
                if len(keyword_hit_pages) >= self.keyword_hit_limit:
                    break

        keep_indices.update(keyword_hit_pages)

        # 4. Extract and verify
        result = [all_pages[i] for i in sorted(keep_indices) if i < len(all_pages)]

        dropped = total - len(result)
        logger.debug(
            "Downsample %s: kept %d/%d pages (dropped %d). "
            "keyword_hit_pages=%d (limit=%d)",
            path.name, len(result), total, dropped,
            len(keyword_hit_pages), self.keyword_hit_limit,
        )
        return result

    def _is_keyword_page(self, text: str) -> bool:
        """
        Return True if page text contains at least one SCORING_KEYWORD.

        Uses substring matching (case-sensitive for Chinese).
        Even a single occurrence is enough.
        """
        return any(kw in text for kw in self.SCORING_KEYWORDS)

    def _compute_sha256(self, path: Path) -> str:
        """Compute SHA256 of raw PDF bytes for dedup fingerprinting."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
