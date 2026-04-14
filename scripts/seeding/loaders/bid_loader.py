"""Bid Loader — real SQLAlchemy upsert for historical_bids.

Handles:
  - Upsert by (historical_tender_id) — one record per tender
  - price_gap_percentage derivation: (our_bid_price - winning_price) / winning_price * 100
  - price_gap_bucket classification: overpriced / slightly_high / winning / underpriced
  - is_sole_bidder = (total_bidders_count == 1)
  - is_postmortem_completed = False on initial import

Author: TIS Seeding Pipeline
"""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.historical import HistoricalBid

logger = logging.getLogger(__name__)


class BidLoader:
    """
    Upserts historical bid records into the historical_bids table.

    One record per (tender × our_company) combination.

    price_gap_percentage formula:
        gap = (our_bid_price - winning_price) / winning_price × 100
        Positive = we overpriced;  Negative = we underpriced (possible win)

    price_gap_bucket thresholds:
        gap < -5%  → 'underpriced'   (we bid aggressively low — possible win)
        -5% to +2% → 'winning'        (optimal competitive zone)
        +2% to +10% → 'slightly_high' (marginally overpriced)
        gap > +10% → 'overpriced'     (significantly overpriced)

    is_sole_bidder: True when total_bidders_count == 1

    Usage:
        loader = BidLoader()
        bid_id = loader.upsert_bid(
            db=db,
            historical_tender_id=tender_id,
            our_bid_price=Decimal("1350000"),
            our_bid_status="lost",
            winning_price=Decimal("1300000"),
            total_bidders_count=5,
        )
    """

    def upsert_bid(self, db: Session, **fields) -> int:
        """
        Insert or update a historical_bid record.

        Args:
            db: SQLAlchemy session (committed by caller).
            **fields: Must include historical_tender_id.
                     Optional: our_bid_price, our_bid_status, winning_price,
                               total_bidders_count, win_rank, bid_file_path, etc.

        Returns:
            bid_id of the upserted record.
        """
        tender_id = fields.get("historical_tender_id")
        if not tender_id:
            raise ValueError("historical_tender_id is required for upsert")

        # ── Derive computed fields ────────────────────────────────────────────
        our_price = fields.get("our_bid_price")
        win_price = fields.get("winning_price")

        if our_price is not None and win_price is not None:
            gap = self._derive_price_gap(our_price, win_price)
            if gap is not None:
                fields["price_gap_percentage"] = float(gap)
                fields["price_gap_bucket"] = self._classify_price_gap(gap)
            else:
                fields["price_gap_percentage"] = None
                fields["price_gap_bucket"] = None
        else:
            fields["price_gap_percentage"] = None
            fields["price_gap_bucket"] = None

        # is_sole_bidder
        total = fields.get("total_bidders_count")
        if total is not None:
            fields["is_sole_bidder"] = total == 1
        else:
            fields["is_sole_bidder"] = False

        # Default: postmortem not done yet
        if "is_postmortem_completed" not in fields:
            fields["is_postmortem_completed"] = False

        # Remove non-column fields used only for computation
        fields.pop("winning_price", None)

        # ── Upsert: INSERT ON CONFLICT DO UPDATE by tender_id ─────────────────
        stmt = insert(HistoricalBid).values(**fields)
        stmt = stmt.on_conflict_do_update(
            index_elements=["historical_tender_id"],
            set_={
                k: v
                for k, v in fields.items()
                if k != "historical_tender_id"
            },
        )
        result = db.execute(stmt)
        db.flush()

        bid_id = result.inserted_primary_key[0] if result.inserted_primary_key else None
        if bid_id is None:
            sel = select(HistoricalBid.id).where(
                HistoricalBid.historical_tender_id == tender_id
            )
            bid_id = db.execute(sel).scalar_one()

        logger.debug("Upserted bid: id=%d tender_id=%d", bid_id, tender_id)
        return int(bid_id)

    def upsert_bid_from_csv_row(
        self,
        db: Session,
        historical_tender_id: int,
        csv_row: dict,
    ) -> int:
        """
        Convenience wrapper: maps CSV row dict to historical_bids columns.

        Expected CSV columns:
            historical_tender_id, our_bid_price, our_bid_status,
            our_bid_submission_date, winning_price, total_bidders_count,
            win_rank, bid_file_path, ...

        Args:
            historical_tender_id: FK to historical_tenders.id.
            csv_row: Dict from outcome CSV row.

        Returns:
            bid_id of the upserted record.
        """
        our_bid_price = self._parse_decimal(csv_row.get("our_bid_price"))
        winning_price = self._parse_decimal(csv_row.get("winning_price"))
        total_bidders = self._parse_int(csv_row.get("total_bidders_count"))
        win_rank = self._parse_int(csv_row.get("win_rank"))
        submission_date = csv_row.get("submission_date")
        bid_status = csv_row.get("our_bid_status", "").strip().lower() or None

        fields: dict[str, Any] = {
            "historical_tender_id": historical_tender_id,
            "our_bid_price": float(our_bid_price) if our_bid_price else None,
            "our_bid_status": bid_status,
            "winning_price": float(winning_price) if winning_price else None,
            "total_bidders_count": total_bidders,
            "win_rank": win_rank,
            "bid_file_path": csv_row.get("bid_file_path"),
        }

        if submission_date:
            fields["our_bid_submission_date"] = submission_date

        logger.info(
            "Upserting bid: tender_id=%d status=%s our_price=%s win_price=%s",
            historical_tender_id, bid_status,
            fields.get("our_bid_price"), fields.get("winning_price"),
        )
        return self.upsert_bid(db=db, **fields)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _derive_price_gap(our_price, winning_price) -> Optional[Decimal]:
        """
        Compute price_gap_percentage = (our - winning) / winning × 100.

        Returns None if winning_price is zero or None.
        Accepts float or Decimal inputs — normalizes to Decimal internally.
        """
        if winning_price is None or winning_price == 0:
            return None
        try:
            our = Decimal(str(our_price))
            win = Decimal(str(winning_price))
            return (our - win) / win * Decimal("100")
        except (InvalidOperation, ZeroDivisionError, ValueError):
            return None

    @staticmethod
    def _classify_price_gap(gap_pct: Decimal) -> str:
        """
        Classify gap_pct into a price_gap_bucket string.

        Args:
            gap_pct: Decimal percentage (positive = we overpriced).

        Returns:
            'underpriced' | 'winning' | 'slightly_high' | 'overpriced'
        """
        try:
            if gap_pct < Decimal("-5"):
                return "underpriced"
            elif gap_pct <= Decimal("2"):
                return "winning"
            elif gap_pct <= Decimal("10"):
                return "slightly_high"
            else:
                return "overpriced"
        except InvalidOperation:
            return "unknown"

    @staticmethod
    def _parse_decimal(v: Any) -> Optional[Decimal]:
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        try:
            return Decimal(str(v).strip())
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _parse_int(v: Any) -> Optional[int]:
        if v is None:
            return None
        try:
            return int(str(v).strip())
        except (ValueError, TypeError):
            return None
