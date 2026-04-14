"""Seeding Pipeline Configuration — all tunable parameters in one place.

Loaded from environment variables with sensible defaults.
Validated at startup — pipeline refuses to run with missing required fields.

Author: TIS Seeding Pipeline
"""
from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SeedingConfig:
    """
    All configuration for the historical data seeding pipeline.

    Environment variables (prefix SEEDING_):
      SEEDING_INPUT_DIR         — Root directory containing .pdf and .docx files
      SEEDING_OUTCOME_CSV       — Path to the business-maintained CSV outcome book
      SEEDING_CHECKPOINT_PATH   — Path to status.json (default: ./status.json)
      SEEDING_DEDUP_DB_PATH     — Path to SHA256 dedup SQLite DB
      SEEDING_DATABASE_URL      — PostgreSQL connection string (sqlalchemy format)
      SEEDING_EMBEDDING_URL     — URL of the embed endpoint (default: http://ai_service:8000/embed)
      SEEDING_BATCH_SIZE         — Chunks per embed+write batch (default: 32)
      SEEDING_MAX_PDF_PAGES     — Downsample threshold: > N pages triggers sampling (default: 100)
      SEEDING_CHUNK_SIZE        — Characters per chunk for rough segmenter (default: 1200)
      SEEDING_HALT_ON_ERROR     — 'true'/'false': halt entire pipeline on first error (default: false)
      SEEDING_LOG_LEVEL         — Python log level: DEBUG/INFO/WARNING/ERROR (default: INFO)

    Required fields (no default):
      SEEDING_INPUT_DIR
      SEEDING_OUTCOME_CSV
      SEEDING_DATABASE_URL
    """

    # ── Paths ────────────────────────────────────────────────────────────────
    input_dir: Path
    outcome_csv_path: Path
    checkpoint_path: Path = field(default_factory=lambda: Path("status.json"))
    dedup_db_path: Path = field(default_factory=lambda: Path("processed.db"))

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql://postgres:Syk0215@db:5432/canteen_system"

    # ── Embedding ───────────────────────────────────────────────────────────
    embedding_url: str = "http://ai_service:8000/embed"
    batch_size: int = 32

    # ── Parser thresholds ────────────────────────────────────────────────────
    max_pdf_pages: int = 100    # > this → downsample (B: >100 pages)
    chunk_size: int = 1200      # rough segmenter char budget

    # ── Fault tolerance ──────────────────────────────────────────────────────
    halt_on_error: bool = False  # if True, raise on first error; else skip and log

    # ── Logging ─────────────────────────────────────────────────────────────
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "SeedingConfig":
        """
        Load configuration from environment variables with validation.

        Returns:
            SeedingConfig instance.

        Raises:
            ValueError: if a required field is missing or invalid.
        """
        def _path(v: str, name: str) -> Path:
            p = Path(v)
            if not p.exists():
                raise ValueError(f"Path does not exist: {name}={v}")
            return p

        def _optional_path(v: str, default: Path) -> Path:
            if not v:
                return default
            return Path(v)

        missing = [k for k in ("SEEDING_INPUT_DIR", "SEEDING_OUTCOME_CSV")
                   if not os.environ.get(k)]
        if missing:
            raise ValueError(
                f"Required environment variables not set: {missing}. "
                "See SeedingConfig.from_env() docstring."
            )

        input_dir = _path(os.environ["SEEDING_INPUT_DIR"], "SEEDING_INPUT_DIR")
        outcome_csv = _path(os.environ["SEEDING_OUTCOME_CSV"], "SEEDING_OUTCOME_CSV")

        cfg = cls(
            input_dir=input_dir,
            outcome_csv_path=outcome_csv,
            checkpoint_path=_optional_path(
                os.environ.get("SEEDING_CHECKPOINT_PATH"), Path("status.json")
            ),
            dedup_db_path=_optional_path(
                os.environ.get("SEEDING_DEDUP_DB_PATH"), Path("processed.db")
            ),
            database_url=os.environ.get(
                "SEEDING_DATABASE_URL",
                "postgresql://postgres:Syk0215@db:5432/canteen_system",
            ),
            embedding_url=os.environ.get("SEEDING_EMBEDDING_URL", "http://ai_service:8000/embed"),
            batch_size=int(os.environ.get("SEEDING_BATCH_SIZE", "32")),
            max_pdf_pages=int(os.environ.get("SEEDING_MAX_PDF_PAGES", "100")),
            chunk_size=int(os.environ.get("SEEDING_CHUNK_SIZE", "1200")),
            halt_on_error=os.environ.get("SEEDING_HALT_ON_ERROR", "false").lower() == "true",
            log_level=os.environ.get("SEEDING_LOG_LEVEL", "INFO"),
        )
        return cfg

    def validate(self) -> None:
        """Runtime validation after construction."""
        if not self.input_dir.is_dir():
            raise ValueError(f"input_dir is not a directory: {self.input_dir}")
        if not self.outcome_csv_path.is_file():
            raise ValueError(f"outcome_csv_path is not a file: {self.outcome_csv_path}")
        if self.batch_size <= 0:
            raise ValueError(f"batch_size must be > 0, got {self.batch_size}")
