"""SHA256-based file deduplication — prevents re-processing the same tender file.

Design: stores fingerprints in a lightweight SQLite DB (not the main PostgreSQL DB).
One table: `processed_files(sha256 TEXT PRIMARY KEY, file_path TEXT, processed_at TEXT)`.

Thread-safety: uses WAL mode and connection per-thread pattern.

Author: TIS Seeding Pipeline
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level lock for thread-safe SQLite writes
_lock = threading.Lock()


class SHA256Dedup:
    """
    Tracks SHA256 fingerprints of processed files to prevent duplicate work.

    Design:
      - Separate SQLite DB from the main PostgreSQL (avoids multi-threaded
        contention on the app DB connection pool).
      - Uses WAL mode for safe concurrent reads during pipeline runs.
      - stores (sha256_hex, file_path, processed_at) per processed file.
      - is_processed(sha256) → True/False (O(1) PRIMARY KEY lookup).

    Usage:
        dedup = SHA256Dedup("/data/seeding/processed.db")
        if not dedup.is_processed(sha256):
            process_file(file_path)
            dedup.mark_processed(file_path, sha256)
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        """Create a new SQLite connection with WAL mode."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        """Create the processed_files table if not exists."""
        with _lock:
            conn = self._conn()
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS processed_files (
                        sha256      TEXT    PRIMARY KEY,
                        file_path   TEXT    NOT NULL,
                        processed_at TEXT    NOT NULL
                    )
                """)
                conn.commit()
            finally:
                conn.close()

    def is_processed(self, sha256_hex: str) -> bool:
        """
        Check if a file has already been processed.

        Args:
            sha256_hex: SHA256 hex digest of the file content.

        Returns:
            True if the file (by content hash) was already processed.
        """
        conn = self._conn()
        try:
            cur = conn.execute(
                "SELECT 1 FROM processed_files WHERE sha256 = ?",
                (sha256_hex,),
            )
            return cur.fetchone() is not None
        finally:
            conn.close()

    def mark_processed(self, file_path: str, sha256_hex: str) -> None:
        """
        Record that a file has been successfully processed.

        Idempotent: INSERT OR REPLACE — safe to call multiple times.

        Args:
            file_path: Original file path (for human audit).
            sha256_hex: SHA256 hex digest of the file content.
        """
        with _lock:
            conn = self._conn()
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO processed_files (sha256, file_path, processed_at) VALUES (?, ?, ?)",
                    (sha256_hex, str(file_path), datetime.utcnow().isoformat()),
                )
                conn.commit()
                logger.debug("Marked processed: %s (%s)", file_path, sha256_hex[:12])
            finally:
                conn.close()

    def get_all(self) -> list[tuple[str, str, str]]:
        """
        Return all processed file records (for audit/debug).

        Returns:
            List of (sha256_hex, file_path, processed_at) tuples.
        """
        conn = self._conn()
        try:
            cur = conn.execute(
                "SELECT sha256, file_path, processed_at FROM processed_files ORDER BY processed_at DESC"
            )
            return cur.fetchall()
        finally:
            conn.close()

    def purge(self, sha256_hex: str) -> bool:
        """
        Remove a single fingerprint (used for reprocessing a specific file).

        Args:
            sha256_hex: SHA256 to remove.

        Returns:
            True if a row was deleted, False if it didn't exist.
        """
        with _lock:
            conn = self._conn()
            try:
                cur = conn.execute(
                    "DELETE FROM processed_files WHERE sha256 = ?",
                    (sha256_hex,),
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

    def count(self) -> int:
        """Return total number of processed fingerprints."""
        conn = self._conn()
        try:
            cur = conn.execute("SELECT COUNT(*) FROM processed_files")
            row = cur.fetchone()
            return row[0] if row else 0
        finally:
            conn.close()
