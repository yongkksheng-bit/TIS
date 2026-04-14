#!/usr/bin/env python3
"""
run_import.py — Historical Data Seeding Pipeline (Phase 3 Main Entry)

Usage:
    python run_import.py                    # resume from checkpoint if exists
    python run_import.py --reset            # clear checkpoint and restart
    python run_import.py --dry-run          # scan files only, no writes

Environment variables (see config.py):
    SEEDING_INPUT_DIR        — Directory containing .pdf / .docx tender files
    SEEDING_OUTCOME_CSV     — Path to the bid-outcome CSV maintained by business
    SEEDING_DATABASE_URL    — PostgreSQL connection string
    SEEDING_EMBEDDING_URL   — Embedding service URL (default: http://ai_service:8000/embed)
    SEEDING_MAX_PDF_PAGES  — Downsample threshold (default: 100)
    SEEDING_BATCH_SIZE      — Embed+write batch size (default: 32)
    SEEDING_HALT_ON_ERROR   — 'true' to stop on first error (default: false)

Exit codes:
    0  — All files processed successfully (or nothing to do)
    1  — Fatal configuration / setup error
    2  — Pipeline reached error state (check status.json errors array)

Pipeline phases (checkpoint.phase):
    init → tenders → bids → chunks → done

Fault-tolerance design:
  1. Checkpoint saved AFTER each file is fully processed (mark_file_processed).
  2. If a file is mid-processing when the process is killed, resume will find
     it in current_file and skip already-written tender_ids in tender_ids dict.
  3. HTTP errors from ai_service: retry up to 3x with backoff; if all fail,
     the chunk is logged as failed but pipeline continues (graceful degradation).
  4. Database errors: logged to checkpoint.errors[] with FATAL flag only
     if halt_on_error=True; otherwise skipped and next file continues.
  5. Dedup: SHA256 checked BEFORE parsing — already-processed files are
     skipped immediately (not re-parsed, not re-embedded).

Author: TIS Seeding Pipeline
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import logging
import os
import sys
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path

# ── Pipeline imports ────────────────────────────────────────────────────────────
from scripts.seeding.config import SeedingConfig
from scripts.seeding.utils.checkpoint import Checkpoint
from scripts.seeding.utils.dedup import SHA256Dedup
from scripts.seeding.utils.outcome_book import OutcomeBook

from scripts.seeding.parsers.pdf_parser import PDFParser, PDFParseResult
from scripts.seeding.parsers.docx_parser import DOCXParser, DOCXParseResult
from scripts.seeding.chunkers.historical_chunker import HistoricalChunker
from scripts.seeding.embedders.historical_embedder import HistoricalEmbeddingEngine
from scripts.seeding.loaders.tender_loader import TenderLoader
from scripts.seeding.loaders.bid_loader import BidLoader
from scripts.seeding.loaders.chunk_loader import ChunkLoader

# ── Logging setup ──────────────────────────────────────────────────────────────

def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


# ── SHA256 helper ──────────────────────────────────────────────────────────────

def sha256_file(path: Path) -> str:
    """Compute SHA256 of a file's raw bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ── File scanner ───────────────────────────────────────────────────────────────

def scan_files(input_dir: Path) -> list[Path]:
    """
    Return sorted list of all .pdf and .docx files in input_dir (recursive).

    Args:
        input_dir: Root directory to scan.

    Returns:
        List of Path objects sorted alphabetically.
    """
    files: list[Path] = []
    for ext in ("*.pdf", "*.docx"):
        files.extend(sorted(input_dir.rglob(ext)))
    return files


# ── Parse dispatch ─────────────────────────────────────────────────────────────

def parse_file(file_path: Path) -> PDFParseResult | DOCXParseResult:
    """
    Dispatch to the appropriate parser based on file extension.

    Returns:
        PDFParseResult for .pdf, DOCXParseResult for .docx.
    """
    if file_path.suffix.lower() == ".pdf":
        return PDFParser().parse(file_path)
    else:
        return DOCXParser().parse(file_path)


# ── Pipeline phase steps ───────────────────────────────────────────────────────

def step_parse_and_load_tender(
    cfg: SeedingConfig,
    file_path: Path,
    outcome_book: OutcomeBook,
    checkpoint: Checkpoint,
) -> int:
    """
    Phase: tenders

    Parse tender file → upsert to historical_tenders → return tender_id.

    On success: marks file processed in checkpoint.
    On error: logs to checkpoint.errors[]; raises or continues per halt_on_error.

    Returns:
        historical_tenders.id for this file.
    """
    tender_loader = TenderLoader()
    # Parse the file
    parse_result = parse_file(file_path)

    if parse_result.error:
        raise RuntimeError(f"Parse failed: {parse_result.error}")

    # Check outcome book for this tender (matched by tender_id if already written,
    # or by a lookup key if the tender was already upserted with a temp ID)
    # The outcome_book uses historical_tender_id as FK; we don't have it yet.
    # We pass the parse_result metadata so tender_loader can match by file_hash.
    tender_id = tender_loader.upsert_tender_from_metadata(
        file_hash=parse_result.sha256,
        project_name=file_path.stem[:200],  # use filename as fallback name
        outcome_book=outcome_book,
        parsed_result=parse_result,
    )
    return tender_id


def step_load_bid_and_chunks(
    cfg: SeedingConfig,
    tender_id: int,
    file_path: Path,
    parse_result: PDFParseResult | DOCXParseResult,
    outcome_book: OutcomeBook,
    db,
    embedder: HistoricalEmbeddingEngine,
    checkpoint: Checkpoint,
    dry_run: bool = False,
) -> int:
    """
    Phase: bids + chunks

    1. If outcome_book has a row for this tender_id:
         - upsert historical_bid record with win_signal metadata
         - extract expert_feedback_text for separate chunking
    2. Rough-segment + fine-chunk the parse result text
    3. For each chunk:
         - determine win_signal from outcome_book (or 'neutral' if no outcome)
         - call chunk_loader.insert_enriched_chunk(...)
         - embed via HistoricalEmbeddingEngine

    Returns:
        Total number of knowledge_chunks written.
    """
    bid_loader = BidLoader()
    chunk_loader = ChunkLoader(db, batch_size=cfg.batch_size)

    # ── V3 HistoricalChunker with LLM insights ───────────────────────────
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    chunker = HistoricalChunker(
        chunk_size=cfg.chunk_size,
        min_segment_chars=500,
        overlap=80,
        enable_llm_insights=bool(deepseek_key),
        deepseek_api_key=deepseek_key,
        max_concurrency=5,
    )

    # Get outcome for this tender (if exists in CSV)
    # Fallback to file_hash lookup if tender_id not found (CSV rows without historical_tender_id)
    outcome = outcome_book.get(tender_id) or outcome_book.get_by_file_hash(parse_result.sha256)
    win_signal = outcome.get("win_signal", "neutral") if outcome else "neutral"
    source_type = "historical_tender"

    # Convert to V3 blocks (handles both DOCX V3 blocks and PDF pages → blocks)
    blocks = _to_blocks(parse_result)
    if not blocks:
        logging.warning("Empty document: %s — skipping chunks", file_path)
        return 0

    # ── Bid record (if outcome exists) ────────────────────────────────────
    if outcome:
        bid_loader.upsert_bid_from_csv_row(
            db=db,
            historical_tender_id=tender_id,
            csv_row={
                "historical_tender_id": tender_id,
                **{k: v for k, v in outcome.items() if k != "win_signal"},
            },
        )
        logging.info(
            "Bid loaded: tender_id=%d win_signal=%s outcome=%s",
            tender_id, win_signal, outcome.get("our_bid_status"),
        )

    # ── Chunk + embed + write loop ──────────────────────────────────────────
    chunks_written = 0
    chunks = chunker.chunk(
        blocks,
        base_metadata={
            "source_file": str(file_path),
            "tender_id": tender_id,
            "win_signal": win_signal,
            "source_type": source_type,
            "region_tags": outcome.get("region_tags") if outcome else None,
            "project_type_tags": outcome.get("project_type_tags") if outcome else None,
        },
    )

    if dry_run:
        logging.info("[DRY RUN] Would write %d chunks for %s", len(chunks), file_path)
        return 0

    for chunk in chunks:
        if not chunk.text.strip():
            continue
        try:
            vectors = embedder.embed_with_retry(chunk.text, max_retries=3)
            if not vectors:
                logging.warning(
                    "Embed failed after retries: chunk_id=%s tender=%d — skipping",
                    chunk.chunk_index, tender_id,
                )
                continue
        except Exception as exc:
            logging.warning(
                "Embed error for tender_id=%d chunk=%d: %s — skipping",
                tender_id, chunk.chunk_index, exc,
            )
            continue

        chunk_loader.insert_enriched_chunk(
            db=db,
            chunk=chunk,
            vector=vectors,
            win_signal=win_signal,
            source_type=source_type,
            source_id=tender_id,
            scoring_dimension_tags=chunk.metadata.get("scoring_dimension_tags"),
            region_tags=chunk.metadata.get("region_tags"),
            project_type_tags=chunk.metadata.get("project_type_tags"),
            is_price_sensitive=_is_price_sensitive_text(chunk.text),
        )
        chunks_written += 1

    # Flush remaining buffer
    flushed = chunk_loader.flush()
    logging.debug("Flushed %d chunks for tender_id=%d", flushed, tender_id)
    return chunks_written


def _to_blocks(parse_result: PDFParseResult | DOCXParseResult) -> list[dict]:
    """
    Convert any parse result to a list of V3-style block dicts.

    V3 HistoricalChunker.chunk() expects list[Block|dict] where each item has
    .block_type ("paragraph"|"table") and .content (str).
    For backwards compatibility, dict-style blocks are also accepted.

    For DOCX (V3): use parse_result.blocks directly (already in document order).
    For PDF: each page is wrapped as one paragraph block.
    """
    # DOCX V3: already has blocks list — extract block_type + content
    if hasattr(parse_result, "blocks") and parse_result.blocks:
        result: list[dict] = []
        for b in parse_result.blocks:
            if hasattr(b, "block_type"):
                result.append({"block_type": b.block_type, "content": b.content})
            else:
                result.append(b)  # already a dict
        return result

    # PDF: each page → one paragraph block
    if hasattr(parse_result, "pages"):
        return [
            {"block_type": "paragraph", "content": page_text}
            for page_text in parse_result.pages
            if page_text.strip()
        ]

    # Legacy: fall back to paragraphs list
    if hasattr(parse_result, "paragraphs"):
        return [
            {"block_type": "paragraph", "content": p}
            for p in parse_result.paragraphs
            if p.strip()
        ]

    # Absolute fallback: treat entire document as one paragraph
    full = getattr(parse_result, "full_text", "") or ""
    return [{"block_type": "paragraph", "content": full}] if full.strip() else []


def _is_price_sensitive_text(text: str) -> bool:
    """Heuristic: tag as price-sensitive if text mentions price-related keywords."""
    price_keywords = ["报价", "价格", "预算", "成本", "优惠", "折扣", "元/", "元\\"]
    return any(kw in text for kw in price_keywords)


# ── Per-file processing ────────────────────────────────────────────────────────

def process_file(
    cfg: SeedingConfig,
    file_path: Path,
    outcome_book: OutcomeBook,
    checkpoint: Checkpoint,
    dedup: SHA256Dedup,
    db,
    dry_run: bool = False,
) -> tuple[bool, int]:
    """
    Process a single tender file end-to-end.

    Returns:
        (success: bool, chunks_written: int)
    """
    # ── Dedup check ──────────────────────────────────────────────────────────
    file_hash = sha256_file(file_path)
    if dedup.is_processed(file_hash):
        checkpoint.mark_file_skipped(str(file_path), f"sha256={file_hash[:12]}")
        logging.info("SKIP (dedup): %s", file_path)
        return True, 0

    if checkpoint.is_file_processed(str(file_path)):
        logging.info("SKIP (checkpoint): %s", file_path)
        return True, 0

    # ── Advance checkpoint to in-progress ──────────────────────────────────
    checkpoint.advance(phase="tenders", current_file=str(file_path), sha256=file_hash)

    # ── Parse ──────────────────────────────────────────────────────────────
    logging.info("Parsing: %s", file_path)
    parse_result = parse_file(file_path)
    if parse_result.error:
        raise RuntimeError(f"Parse failed: {parse_result.error}")

    # Update dedup fingerprint (done early so crash-resume won't re-parse)
    dedup.mark_processed(str(file_path), file_hash)

    # ── Load tender ─────────────────────────────────────────────────────────
    tender_loader = TenderLoader()
    tender_id = tender_loader.upsert_tender_from_metadata(
        db=db,
        file_hash=parse_result.sha256,
        project_name=file_path.stem[:200],
        outcome_book=outcome_book,
        parsed_result=parse_result,
    )
    logging.info("Tender upserted: tender_id=%d for %s", tender_id, file_path.name)

    # ── Load bid + write chunks ────────────────────────────────────────────
    chunks_written = step_load_bid_and_chunks(
        cfg=cfg,
        tender_id=tender_id,
        file_path=file_path,
        parse_result=parse_result,
        outcome_book=outcome_book,
        db=db,
        embedder=HistoricalEmbeddingEngine(
            base_url=cfg.embedding_url,
            batch_size=cfg.batch_size,
        ),
        checkpoint=checkpoint,
        dry_run=dry_run,
    )

    # ── Mark complete ──────────────────────────────────────────────────────
    checkpoint.mark_file_processed(str(file_path), tender_id, chunks_written)
    logging.info(
        "DONE: %s → tender_id=%d chunks=%d",
        file_path.name, tender_id, chunks_written,
    )
    return True, chunks_written


# ── Main pipeline ──────────────────────────────────────────────────────────────

def run(cfg: SeedingConfig, dry_run: bool = False, reset: bool = False) -> None:
    """
    Run the full seeding pipeline.

    Steps:
      1. Load or init checkpoint
      2. Scan input directory for files
      3. Filter out already-processed files (checkpoint + dedup)
      4. For each remaining file: process_file() with fault-tolerance
      5. On completion: checkpoint.phase = 'done'
    """
    logger = logging.getLogger("pipeline")

    # ── Init checkpoint ──────────────────────────────────────────────────────
    if reset:
        checkpoint = Checkpoint.load(cfg.checkpoint_path)
        checkpoint.reset()
        logger.warning("Checkpoint reset — starting from scratch.")
    else:
        checkpoint = Checkpoint.load(cfg.checkpoint_path)

    if checkpoint.phase == "done":
        logger.info("Pipeline already complete. Use --reset to re-run.")
        return

    # ── Init dedup ───────────────────────────────────────────────────────────
    dedup = SHA256Dedup(cfg.dedup_db_path)
    logger.info("Dedup DB: %d files already processed", dedup.count())

    # ── Load outcome book ────────────────────────────────────────────────────
    outcome_book = OutcomeBook.from_csv(cfg.outcome_csv_path)
    logger.info("Outcome book loaded: %d rows", len(outcome_book))

    # ── Connect to application DB ───────────────────────────────────────────
    # SQLAlchemy session for loaders
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker, Session
    engine = create_engine(cfg.database_url, pool_size=5, max_overflow=10)
    SessionLocal = sessionmaker(bind=engine)
    db: Session = SessionLocal()
    logger.info("DB connected: %s", cfg.database_url.split("@")[-1])

    try:
        # ── Scan files ─────────────────────────────────────────────────────────
        all_files = scan_files(cfg.input_dir)
        total_files = len(all_files)
        logger.info("Input directory: %s (%d files found)", cfg.input_dir, total_files)

        if total_files == 0:
            logger.info("No input files found — nothing to do.")
            checkpoint._data["phase"] = "done"
            checkpoint._save()
            return

        # ── Determine resume point ─────────────────────────────────────────────
        processed = set(checkpoint.processed_files)
        files_to_process = [
            f for f in all_files
            if str(f) not in processed
        ]

        if not files_to_process:
            logger.info("All files already processed — nothing to do.")
            checkpoint._data["phase"] = "done"
            checkpoint._save()
            return

        resume_file = checkpoint.current_file
        if resume_file:
            resume_idx = next(
                (i for i, f in enumerate(files_to_process) if str(f) == resume_file),
                None,
            )
            if resume_idx is not None:
                logger.info("Resuming from: %s (index %d)", resume_file, resume_idx)
                files_to_process = files_to_process[resume_idx:]
            else:
                # current_file not in list → checkpoint stale, start from beginning
                logger.warning("Stale checkpoint (current_file not found) — starting fresh.")
                files_to_process = files_to_process

        logger.info(
            "Pipeline start: %d files to process (total=%d, done=%d)",
            len(files_to_process), total_files, len(processed),
        )

        # ── Main processing loop ────────────────────────────────────────────────
        total_chunks = checkpoint.total_chunks
        errors = 0

        for idx, file_path in enumerate(files_to_process, start=1):
            logger.info(
                "[%d/%d] Processing: %s",
                idx, len(files_to_process), file_path.name,
            )
            try:
                success, chunks = process_file(
                    cfg=cfg,
                    file_path=file_path,
                    outcome_book=outcome_book,
                    checkpoint=checkpoint,
                    dedup=dedup,
                    db=db,
                    dry_run=dry_run,
                )
                total_chunks += chunks
            except Exception as exc:
                errors += 1
                err_msg = f"{type(exc).__name__}: {exc}"
                logger.error("ERROR processing %s: %s", file_path, err_msg)
                checkpoint.add_error(str(file_path), err_msg, fatal=cfg.halt_on_error)
                if cfg.halt_on_error:
                    raise
                # Continue to next file

        # ── Mark pipeline complete ─────────────────────────────────────────────
        if errors == 0 or not cfg.halt_on_error:
            checkpoint._data["phase"] = "done"
            checkpoint._save()
            logger.info(
                "Pipeline complete. Files=%d Chunks=%d Errors=%d",
                len(checkpoint.processed_files), total_chunks, errors,
            )
        else:
            logger.error(
                "Pipeline halted due to errors. Errors=%d — check status.json errors[]",
                errors,
            )
            sys.exit(2)

    finally:
        db.close()
        engine.dispose()


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="TIS Historical Data Seeding Pipeline (Phase 3)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_import.py                    # Resume from checkpoint
  python run_import.py --reset           # Clear checkpoint and restart
  python run_import.py --dry-run          # Scan files without writing
  SEEDING_INPUT_DIR=/data/tenders python run_import.py
        """,
    )
    parser.add_argument("--reset", action="store_true",
                        help="Clear checkpoint and start from scratch")
    parser.add_argument("--dry-run", action="store_true",
                        help="Scan files and log what would be done, without writing to DB")
    args = parser.parse_args()

    try:
        cfg = SeedingConfig.from_env()
        cfg.validate()
    except ValueError as e:
        print(f"[CONFIG ERROR] {e}", file=sys.stderr)
        print("Required env vars: SEEDING_INPUT_DIR, SEEDING_OUTCOME_CSV", file=sys.stderr)
        sys.exit(1)

    setup_logging(cfg.log_level)

    try:
        run(cfg, dry_run=args.dry_run, reset=args.reset)
    except Exception as exc:
        if cfg.halt_on_error:
            raise
        logging.critical("Fatal pipeline error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
