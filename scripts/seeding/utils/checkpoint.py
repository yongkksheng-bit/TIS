"""Checkpoint — JSON-based fault-tolerance and resume logic for the seeding pipeline.

Design: one status.json file at the pipeline root.
Atomic writes via rename(2) — crash-safe even if process is killed mid-write.

Schema:
{
  "pipeline_version": "1.0",
  "phase": "chunks" | "tenders" | "bids" | "done" | "error",
  "current_file": "/absolute/path/to/file.pdf",
  "current_file_sha256": "abc123...",
  "processed_files": ["file1.pdf", "file2.pdf", ...],
  "skipped_files": ["file3.pdf (sha256 collision)"],
  "tender_ids": {"/path/to/file.pdf": 42, ...},
  "total_chunks_written": 1847,
  "started_at": "2026-04-13T08:00:00Z",
  "last_updated_at": "2026-04-13T10:30:00Z",
  "errors": [
    {"file": "corrupt.pdf", "error": "PDF extraction failed: invalid header", "ts": "..."}
  ]
}

Resume logic:
  1. Load checkpoint on startup.
  2. If current_file is non-null and phase != "done":
       → resume from that file (re-parse, skip already-written tender_ids).
  3. If errors contain FATAL markers → halt and report.
  4. Normal run: update checkpoint after each file.

Author: TIS Seeding Pipeline
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()


class CheckpointError(Exception):
    """Raised on checkpoint corruption or invalid state."""
    pass


class Checkpoint:
    """
    JSON state machine for resumable seeding pipeline execution.

    Thread-safety: uses a threading.Lock so concurrent workers
    can't corrupt the checkpoint file.

    Atomic write: writes to a temp file then os.rename() to target.
    This guarantees the checkpoint is never in a half-written state.

    Usage:
        ck = Checkpoint.load("/data/seeding/status.json")
        if ck.phase == "done":
            print("All done.")
            return
        # ... process file ...
        ck.advance(phase="chunks", current_file=next_file)
    """

    CURRENT_VERSION = "1.0"

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._data: dict[str, Any] = {}

    # ── Factory ──────────────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: str | Path) -> "Checkpoint":
        """
        Load an existing checkpoint, or create a fresh one if none exists.

        Args:
            path: Path to the status.json file.

        Returns:
            Checkpoint instance (new or resumed).

        Raises:
            CheckpointError: if the file exists but is malformed JSON.
        """
        ck = cls(path)
        if ck.path.exists():
            try:
                with open(ck.path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if not isinstance(raw, dict):
                    raise CheckpointError("status.json must be a JSON object")
                ck._data = raw
                logger.info(
                    "Resuming checkpoint: phase=%s, files=%d, chunks=%d",
                    ck._data.get("phase"),
                    len(ck._data.get("processed_files", [])),
                    ck._data.get("total_chunks_written", 0),
                )
            except (json.JSONDecodeError, OSError) as e:
                raise CheckpointError(f"Cannot read checkpoint: {e}")
        else:
            ck._init_fresh()
        return ck

    def _init_fresh(self) -> None:
        """Initialize a fresh checkpoint with default structure."""
        self._data = {
            "pipeline_version": self.CURRENT_VERSION,
            "phase": "init",
            "current_file": None,
            "current_file_sha256": None,
            "processed_files": [],
            "skipped_files": [],
            "tender_ids": {},
            "total_chunks_written": 0,
            "started_at": datetime.utcnow().isoformat() + "Z",
            "last_updated_at": datetime.utcnow().isoformat() + "Z",
            "errors": [],
        }
        self._save()

    # ── Core accessors ──────────────────────────────────────────────────────

    @property
    def phase(self) -> str:
        return self._data.get("phase", "init")

    @property
    def current_file(self) -> Optional[str]:
        return self._data.get("current_file")

    @property
    def current_sha256(self) -> Optional[str]:
        return self._data.get("current_file_sha256")

    @property
    def processed_files(self) -> list[str]:
        return self._data.get("processed_files", [])

    @property
    def tender_ids(self) -> dict[str, int]:
        return self._data.get("tender_ids", {})

    @property
    def total_chunks(self) -> int:
        return self._data.get("total_chunks_written", 0)

    @property
    def errors(self) -> list[dict]:
        return self._data.get("errors", [])

    @property
    def is_done(self) -> bool:
        return self.phase == "done"

    @property
    def is_resumable(self) -> bool:
        """True if there's meaningful work to resume."""
        return self.phase in ("init", "tenders", "bids", "chunks") and (
            self.current_file is not None or len(self.processed_files) > 0
        )

    # ── State mutations ─────────────────────────────────────────────────────

    def is_file_processed(self, file_path: str) -> bool:
        """Return True if this exact file path has already been fully processed."""
        return str(file_path) in self.processed_files

    def get_tender_id(self, file_path: str) -> Optional[int]:
        """Return the tender_id assigned to this file, if any."""
        return self.tender_ids.get(str(file_path))

    def mark_file_processed(
        self,
        file_path: str,
        tender_id: int,
        chunks_written: int = 0,
    ) -> None:
        """
        Mark a file as fully processed and advance phase if needed.

        Args:
            file_path: Absolute path to the processed file.
            tender_id: historical_tender.id assigned to this file.
            chunks_written: Number of knowledge_chunks written for this file.
        """
        with _lock:
            if str(file_path) not in self._data["processed_files"]:
                self._data["processed_files"].append(str(file_path))
            self._data["tender_ids"][str(file_path)] = tender_id
            self._data["total_chunks_written"] += chunks_written
            self._data["last_updated_at"] = datetime.utcnow().isoformat() + "Z"
            self._data["current_file"] = None
            self._data["current_file_sha256"] = None
            self._save()

    def mark_file_skipped(self, file_path: str, reason: str) -> None:
        """Record a file that was intentionally skipped (e.g., dedup)."""
        with _lock:
            if str(file_path) not in self._data.get("skipped_files", []):
                self._data.setdefault("skipped_files", []).append(f"{file_path} ({reason})")
            self._data["last_updated_at"] = datetime.utcnow().isoformat() + "Z"
            self._save()

    def advance(self, phase: str, current_file: str, sha256: str) -> None:
        """
        Advance pipeline to a new phase, marking current_file as in-progress.

        Call this BEFORE processing a new file — it marks the file as
        "currently being processed" so resume can find it.

        Args:
            phase: 'tenders' | 'bids' | 'chunks' | 'done'
            current_file: Absolute path of the file being processed.
            sha256: SHA256 of the file content (for dedup verification on resume).
        """
        with _lock:
            self._data["phase"] = phase
            self._data["current_file"] = str(current_file)
            self._data["current_file_sha256"] = sha256
            self._data["last_updated_at"] = datetime.utcnow().isoformat() + "Z"
            self._save()

    def add_error(self, file_path: str, error_message: str, fatal: bool = False) -> None:
        """
        Log an error for a specific file.

        Args:
            file_path: File that caused the error.
            error_message: Human-readable error description.
            fatal: If True, marks pipeline phase as 'error' to halt on resume.
        """
        with _lock:
            self._data.setdefault("errors", []).append({
                "file": str(file_path),
                "error": error_message,
                "fatal": fatal,
                "ts": datetime.utcnow().isoformat() + "Z",
            })
            if fatal:
                self._data["phase"] = "error"
            self._data["last_updated_at"] = datetime.utcnow().isoformat() + "Z"
            self._save()

    def reset(self) -> None:
        """
        Clear the checkpoint and start fresh. Use with caution.

        Backs up the current checkpoint to status.json.bak before resetting.
        """
        with _lock:
            backup = self.path.with_suffix(".json.bak")
            if self.path.exists():
                shutil.copy2(self.path, backup)
                logger.info("Checkpoint backed up to %s", backup)
            self._init_fresh()
            logger.warning("Checkpoint reset — pipeline will restart from beginning.")

    # ── Atomic write ────────────────────────────────────────────────────────

    def _save(self) -> None:
        """Atomically write checkpoint to disk (write-to-temp + rename)."""
        tmp = self.path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)  # atomic on POSIX and Windows (Python 3.3+)

    def __repr__(self) -> str:
        return (
            f"<Checkpoint phase={self.phase!r} files={len(self.processed_files)} "
            f"chunks={self.total_chunks} errors={len(self.errors)}>"
        )
