"""Outcome Book Loader — reads the historical bid outcome CSV maintained by business.

Schema (CSV columns, all optional except historical_tender_id):
    historical_tender_id   — FK to historical_tenders.id (REQUIRED)
    our_bid_status         — 'won' | 'lost' | 'partial_win' | 'abandoned'
    our_bid_price          — Decimal, our quoted price in CNY
    winning_price         — Decimal, the market winning price
    total_bidders_count   — int, total bidders in this tender
    win_rank               — int, our rank (1=winner)
    submission_date        — str, ISO date "YYYY-MM-DD"
    loss_root_cause_tags   — JSON array string, e.g. '["报价偏高","资质不足"]'
    win_breakthrough_tags  — JSON array string, e.g. '["冷链方案差异化","历史业绩丰富"]'
    key_win_factors        — JSON array string
    key_loss_factors       — JSON array string
    score_received         — Decimal, our total score received
    score_max              — Decimal, max possible score
    technical_score         — Decimal, our technical score
    price_score             — Decimal, our price score
    expert_feedback_text   — str, free-text expert review (long)
    confidential_level      — 'internal' | 'confidential' | 'public'
    bid_file_path           — str, path to our submitted bid document (optional)
    notes                  — str, free-text notes

win_signal derivation:
    our_bid_status == 'won'  → win_signal = 'positive'
    our_bid_status == 'lost' → win_signal = 'negative'
    our_bid_status == 'partial_win' → win_signal = 'neutral'
    otherwise                  → win_signal = 'neutral'

Author: TIS Seeding Pipeline
"""
from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class OutcomeBook:
    """
    In-memory lookup table for historical bid outcomes.

    Loaded once at startup from the CSV file maintained by business users.
    Provides O(1) lookup by historical_tender_id.

    Attributes:
        rows: dict[int, dict] — keyed by historical_tender_id
        all_loss_tags: list[str] — union of all loss_root_cause_tags across all rows
        all_win_tags: list[str] — union of all win_breakthrough_tags across all rows
    """

    def __init__(self, rows: dict[int, dict]):
        self.rows = rows
        # Pre-compute tag unions for quick existence checks
        self.all_loss_tags: set[str] = set()
        self.all_win_tags: set[str] = set()
        for row in rows.values():
            self.all_loss_tags.update(row.get("loss_root_cause_tags", []))
            self.all_win_tags.update(row.get("win_breakthrough_tags", []))
        # Secondary index: file_hash → row (populated by from_csv)
        self._rows_by_hash: dict[str, dict] = {}
        # Tertiary index: project_name → row (populated by from_csv)
        self._rows_by_project: dict[str, dict] = {}

    @classmethod
    def from_csv(cls, csv_path: str | Path) -> "OutcomeBook":
        """
        Load the outcome book from a CSV file.

        Args:
            csv_path: Path to the CSV file.

        Returns:
            OutcomeBook instance.

        Raises:
            FileNotFoundError: if the CSV doesn't exist.
            ValueError: if required column 'historical_tender_id' is missing.
        """
        rows: dict[int, dict] = {}
        # Secondary index: file_hash → row (for tender_file_name lookup)
        rows_by_hash: dict[str, dict] = {}
        # Tertiary index: project_name → row (for bid file resolution)
        rows_by_project: dict[str, dict] = {}

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for lineno, raw_row in enumerate(reader, start=2):  # start=2 (header=1)
                tender_id_str = raw_row.get("historical_tender_id", "").strip()
                file_hash_str = raw_row.get("tender_file_hash", "").strip()
                # CSV header has trailing space: "tender_file_name " (key has trailing space)
                tender_file_name = raw_row.get("tender_file_name", "").strip() or raw_row.get("tender_file_name ", "").strip()
                project_name = raw_row.get("project_name", "").strip()
                # Accept row if it has tender_id, file_hash, tender_file_name, OR project_name
                # (rows can be indexed by project_name even without other identifiers)
                if not tender_id_str and not file_hash_str and not tender_file_name and not project_name:
                    continue  # skip rows without any identifier

                tender_id: Optional[int] = None
                if tender_id_str:
                    try:
                        tender_id = int(tender_id_str)
                    except ValueError:
                        logger.warning(
                            "Line %d: invalid tender_id=%r — skipping",
                            lineno, tender_id_str,
                        )
                        continue

                row = cls._normalize_row(raw_row)
                row["tender_file_hash"] = file_hash_str
                row["tender_file_name"] = tender_file_name

                # Primary: use tender_id if available
                if tender_id is not None:
                    rows[tender_id] = row
                # Secondary: use file_hash if available (sentinel key 0)
                if file_hash_str:
                    rows_by_hash[file_hash_str] = row
                # Tertiary: tender_file_name maps to SHA256 of that file on disk
                if tender_file_name and not file_hash_str:
                    # Compute hash from the actual file on disk if it exists
                    import os
                    possible_paths = [
                        Path(csv_path).parent / "tenders" / tender_file_name,
                        Path(csv_path).parent / tender_file_name,
                    ]
                    for p in possible_paths:
                        if p.exists():
                            import hashlib
                            h = hashlib.sha256()
                            with open(p, "rb") as fh:
                                for chunk in iter(lambda: fh.read(8192), b""):
                                    h.update(chunk)
                            computed_hash = h.hexdigest()
                            row["tender_file_hash"] = computed_hash
                            rows_by_hash[computed_hash] = row
                            logger.debug(
                                "Matched tender_file_name %r → SHA256=%s",
                                tender_file_name, computed_hash[:16],
                            )
                            break
                    else:
                        logger.debug(
                            "tender_file_name %r has no matching file on disk — skipping hash lookup",
                            tender_file_name,
                        )

                # Quaternary: index by project_name for bid file resolution
                project_name = raw_row.get("project_name", "").strip()
                if project_name:
                    rows_by_project[project_name] = row
                    # Also strip common suffixes and index as fallback
                    stripped = _strip_doc_suffix(project_name)
                    if stripped and stripped != project_name:
                        rows_by_project[stripped] = row

        logger.info(
            "Loaded outcome book: %d rows (by tender_id), %d rows (by file_hash), %d rows (by project_name)",
            len(rows), len(rows_by_hash), len(rows_by_project),
        )

        instance = cls(rows)
        # Attach secondary hash index for get_by_file_hash
        instance._rows_by_hash = rows_by_hash
        # Attach tertiary project_name index for get_by_project_name
        instance._rows_by_project = rows_by_project
        return instance

    @classmethod
    def _normalize_row(cls, raw_row: dict[str, str]) -> dict[str, Any]:
        """
        Parse and normalize a raw CSV row dict.

        Converts:
          - Decimal strings → Decimal
          - JSON array strings → list[str]
          - Empty strings → None
          - ISO date strings → datetime.date
        """
        def _dec(v: str) -> Optional[Decimal]:
            v = v.strip()
            if not v:
                return None
            try:
                return Decimal(v)
            except InvalidOperation:
                return None

        def _json_list(v: str) -> list[str]:
            v = v.strip()
            if not v:
                return []
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
                return []
            except (json.JSONDecodeError, TypeError):
                return []

        bid_status = raw_row.get("our_bid_status", "").strip().lower()
        if bid_status == "won":
            win_signal = "positive"
        elif bid_status in ("lost", "failed"):
            win_signal = "negative"
        else:
            win_signal = "neutral"

        return {
            "our_bid_status": bid_status or None,
            "win_signal": win_signal,
            "our_bid_price": _dec(raw_row.get("our_bid_price", "")),
            "winning_price": _dec(raw_row.get("winning_price", "")),
            "total_bidders_count": cls._int_or_none(raw_row.get("total_bidders_count", "")),
            "win_rank": cls._int_or_none(raw_row.get("win_rank", "")),
            "submission_date": cls._date_or_none(raw_row.get("submission_date", "")),
            "loss_root_cause_tags": _json_list(raw_row.get("loss_root_cause_tags", "")),
            "win_breakthrough_tags": _json_list(raw_row.get("win_breakthrough_tags", "")),
            "key_win_factors": _json_list(raw_row.get("key_win_factors", "")),
            "key_loss_factors": _json_list(raw_row.get("key_loss_factors", "")),
            "score_received": _dec(raw_row.get("score_received", "")),
            "score_max": _dec(raw_row.get("score_max", "")),
            "technical_score": _dec(raw_row.get("technical_score", "")),
            "price_score": _dec(raw_row.get("price_score", "")),
            "expert_feedback_text": raw_row.get("expert_feedback_text", "").strip() or None,
            "confidential_level": raw_row.get("confidential_level", "").strip() or "internal",
            "bid_file_path": raw_row.get("bid_file_path", "").strip() or None,
            "notes": raw_row.get("notes", "").strip() or None,
        }

    @staticmethod
    def _int_or_none(v: str) -> Optional[int]:
        v = v.strip()
        if not v:
            return None
        try:
            return int(v)
        except ValueError:
            return None

    @staticmethod
    def _date_or_none(v: str) -> Optional[str]:
        v = v.strip()
        if not v:
            return None
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
            try:
                dt = datetime.strptime(v, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
        return None

    def get(self, tender_id: int) -> Optional[dict[str, Any]]:
        """Get the outcome row for a specific tender, or None if not found."""
        return self.rows.get(tender_id)

    def get_by_file_hash(self, file_hash: str) -> Optional[dict[str, Any]]:
        """Get the first outcome row whose tender_file_hash matches, or None."""
        return self._rows_by_hash.get(file_hash.strip()) or None

    def __contains__(self, tender_id: int) -> bool:
        return tender_id in self.rows

    def __len__(self) -> int:
        return len(self.rows)

    def get_by_project_name(self, project_name: str) -> Optional[dict[str, Any]]:
        """
        Get the outcome row for a project, with suffix-stripping fallback.

        This enables bid files (whose project_name in DB ends with _投标文件)
        to match outcome_book entries whose project_name is the base name.

        Args:
            project_name: The project name to look up (may have _投标文件/_招标文件 suffix).

        Returns:
            The outcome row if found, otherwise None.
        """
        if not project_name:
            return None
        project_name = project_name.strip()
        # Try exact match first
        if project_name in self._rows_by_project:
            return self._rows_by_project[project_name]
        # Fallback: strip suffix and try again
        stripped = _strip_doc_suffix(project_name)
        if stripped and stripped != project_name:
            return self._rows_by_project.get(stripped)
        return None


def _strip_doc_suffix(name: str) -> str:
    """
    Strip common document suffixes from a filename stem.

    Removes: _投标文件, _招标文件, _价格文件, _资格证明文件, _投标书, _采购包 N
    """
    suffixes = [
        "_投标文件",
        "_招标文件",
        "_价格文件",
        "_资格证明文件",
        "_投标书",
    ]
    for s in suffixes:
        if name.endswith(s):
            return name[: -len(s)]
    # Handle "_采购包 N" pattern (e.g., "_采购包 1")
    import re
    m = re.search(r"_采购包\s*\d+$", name)
    if m:
        return name[: m.start()]
    return name
