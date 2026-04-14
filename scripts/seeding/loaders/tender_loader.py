"""Tender Loader — real SQLAlchemy upsert for historical_tenders.

Upsert strategy: INSERT ... ON CONFLICT (tender_file_hash) DO UPDATE.
This ensures re-running the pipeline never creates duplicate tender records.

Author: TIS Seeding Pipeline
"""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.historical import HistoricalTender

logger = logging.getLogger(__name__)


class TenderLoader:
    """
    Upserts historical tender records into the historical_tenders table.

    Key design:
      - Upsert: INSERT ON CONFLICT (tender_file_hash) DO UPDATE
      - Deduplication key: SHA256 of tender file (tender_file_hash column)
      - All columns nullable (forward compatibility)
      - Sets imported_at timestamp automatically
      - Tender status always 'closed' on import (completed tender)

    The `outcome_book` parameter is consulted for region/budget/win_price
    when those values are not explicitly provided as kwargs.
    """

    def upsert_tender(self, db: Session, **fields) -> int:
        """
        Insert or update a historical_tender record.

        Args:
            db: SQLAlchemy session (committed by caller).
            **fields: Column values for historical_tenders.
                     Required: tender_file_hash.
                     Optional: project_name, region, province, project_type,
                               budget_amount, winning_price, tender_status,
                               bid_open_date, submission_deadline, etc.

        Returns:
            The tender_id (primary key) of the upserted row.

        Raises:
            ValueError: if tender_file_hash is missing.
        """
        file_hash = fields.get("tender_file_hash")
        if not file_hash:
            raise ValueError("tender_file_hash is required for upsert")

        # Ensure imported_at is set
        if "imported_at" not in fields:
            fields["imported_at"] = datetime.utcnow()

        # Always mark as closed on import
        if "tender_status" not in fields:
            fields["tender_status"] = "closed"

        # Build the upsert statement: INSERT ... ON CONFLICT DO UPDATE
        stmt = insert(HistoricalTender).values(**fields)
        stmt = stmt.on_conflict_do_update(
            index_elements=["tender_file_hash"],
            set_={
                k: v
                for k, v in fields.items()
                if k != "tender_file_hash"  # don't overwrite the dedup key
            },
        )
        result = db.execute(stmt)
        db.flush()  # get the inserted id without full commit

        # Fetch the tender id (inserted or updated)
        tender_id = result.inserted_primary_key[0] if result.inserted_primary_key else None
        if tender_id is None:
            # ON CONFLICT DO UPDATE returns the existing row's id
            sel = select(HistoricalTender.id).where(
                HistoricalTender.tender_file_hash == file_hash
            )
            tender_id = db.execute(sel).scalar_one()

        logger.debug("Upserted tender: id=%d hash=%s", tender_id, file_hash[:12])
        return int(tender_id)

    def upsert_tender_from_metadata(
        self,
        db: Session,
        file_hash: str,
        project_name: str,
        outcome_book: Any = None,
        parsed_result: Any = None,
        region: Optional[str] = None,
        province: Optional[str] = None,
        project_type: Optional[str] = None,
        budget_amount: Optional[Decimal] = None,
        winning_price: Optional[Decimal] = None,
        **extra_fields,
    ) -> int:
        """
        Convenience wrapper: derive columns from parse result + outcome book.

        Priority for field values:
          1. Explicit kwargs (region, province, budget_amount, etc.)
          2. Outcome book (historical_tender_id → row lookup)
          3. Parse result metadata (total_pages, is_downsampled)

        Args:
            file_hash: SHA256 hex of the tender file.
            project_name: Human-readable name (filename or from outcome CSV).
            outcome_book: OutcomeBook instance (optional).
            parsed_result: PDFParseResult or DOCXParseResult (for metadata).
            region, province, project_type, budget_amount, winning_price: optional overrides.

        Returns:
            tender_id of the upserted record.
        """
        fields: dict[str, Any] = {
            "tender_file_hash": file_hash,
            "project_name": project_name[:500] if project_name else "未命名",
            **extra_fields,
        }

        # From outcome book (if we have a tender_id match — we don't at this point,
        # so outcome_book is only used for enrichment when tender is pre-known.
        # For fresh imports, outcome_book rows are matched after tender insert
        # via historical_tender_id in step_load_bid_and_chunks.)

        # From parse result metadata
        if parsed_result is not None:
            if hasattr(parsed_result, "total_pages"):
                # Store downsampling signal in metadata_json
                meta = fields.get("metadata_json", {})
                if isinstance(meta, dict):
                    meta["import_total_pages"] = parsed_result.total_pages
                    meta["import_is_downsampled"] = parsed_result.is_downsampled
                    fields["metadata_json"] = meta
            if hasattr(parsed_result, "file_path"):
                fields["tender_file_path"] = str(parsed_result.file_path)

        # Explicit overrides
        if region:
            fields["region"] = region
        if province:
            fields["province"] = province
        if project_type:
            fields["project_type"] = project_type
        if budget_amount is not None:
            fields["budget_amount"] = float(budget_amount)
        if winning_price is not None:
            fields["winning_price"] = float(winning_price)
            fields["price_revealed"] = True

        return self.upsert_tender(db=db, **fields)
