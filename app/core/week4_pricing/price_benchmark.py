"""Price Benchmark Analytics — historical market intelligence for pricing decisions.

Queries historical_tenders + historical_bids to compute market-level statistics
that inform A/B/C scenario generation in the game theory model.

Queries ONLY closed tenders with revealed winning prices.
Does NOT touch the active Project table (hard isolation).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select, case, literal, Integer
from sqlalchemy.orm import Session

from app.models.historical import HistoricalTender, HistoricalBid


# ─── Market Heat Context (dataclass) ─────────────────────────────────────────


@dataclass
class MarketHeatContext:
    """
    Market intelligence derived from historical bid data.

    All numeric fields default to None when insufficient data exists —
    callers MUST handle None gracefully (see default() fallback).
    """
    region: str
    project_type: str

    # ── Discount rate stats ─────────────────────────────────────────────────
    avg_discount_rate: Optional[float] = None
    """Mean (winning_price / budget_amount) across historical tenders. None if N=0."""

    median_discount_rate: Optional[float] = None
    """Median discount rate. More robust to outliers than mean."""

    # ── Bidder count stats ───────────────────────────────────────────────────
    bidder_count_avg: Optional[float] = None
    """Mean total_bidders_count across won/lost bids. None if N=0."""

    bidder_count_median: Optional[float] = None
    """Median bidder count."""

    # ── Competitive price intelligence ───────────────────────────────────────
    expected_competitive_price: Optional[Decimal] = None
    """
    Expected market-clearing price as a DISCOUNT MULTIPLIER (winning_price / budget).
    Stored as Decimal to avoid float precision loss.
    Callers multiply this by their budget to get the expected_competitive_price in Yuan.

    Example: budget=1_500_000, expected_competitive_price=Decimal('0.87')
             → expected_competitive_price_in_yuan = 1_500_000 * 0.87 = 1_305_000
    """

    # ── Win rate stats ──────────────────────────────────────────────────────
    historical_win_rate: Optional[float] = None
    """Fraction of our historical bids that won (outcome='won'). None if N=0."""

    sample_size: int = 0
    """Number of historical bids used to compute these stats. 0 = no data."""

    # ── Price gap distribution ───────────────────────────────────────────────
    avg_price_gap_pct: Optional[float] = None
    """Mean price_gap_percentage across our bids. Positive=we overpriced."""

    price_gap_bucket_distribution: dict[str, int] = field(default_factory=dict)
    """Count of our bids by price_gap_bucket (overpriced/slightly_high/winning/underpriced)."""

    @classmethod
    def default(cls, region: str, project_type: str) -> "MarketHeatContext":
        """
        Safe fallback when no historical data exists.
        Returns a 'cold-start' context with all analytics = None / 0,
        signaling to callers that they should use cost-plus pricing.
        """
        return cls(region=region, project_type=project_type, sample_size=0)

    @property
    def has_data(self) -> bool:
        """True if at least one historical bid record exists."""
        return self.sample_size > 0


# ─── Price Benchmark Cache ────────────────────────────────────────────────────


class PriceBenchmarkCache:
    """
    Queries historical_tenders + historical_bids to produce MarketHeatContext.

    Design principles:
    - Safe division: all SQL aggregations guard against zero-count via NULLIF
    - Null-safe: returns MarketHeatContext.default() when no data found
    - Hard isolation: NEVER queries the active Project table
    - Read-only: all queries use SELECT, no mutations
    """

    def __init__(self, db: Session):
        self.db = db

    def get_market_context(
        self,
        region: str,
        project_type: str,
    ) -> MarketHeatContext:
        """
        Compute market heat statistics for a (region, project_type) combination.

        Queries historical_tenders filtered by:
          - region = exact match
          - project_type = exact match
          - tender_status = 'closed'
          - price_revealed = True  (only where we know the winning price)
          - winning_price IS NOT NULL

        Then joins to historical_bids to get our bid outcomes and competitive position.

        Args:
            region: e.g. '广东省', '华中地区'
            project_type: e.g. 'service', 'goods', 'engineering'

        Returns:
            MarketHeatContext (never raises — degrades gracefully to .default())
        """
        try:
            return self._compute(region, project_type)
        except Exception:
            # Graceful degradation: DB errors fall back to null context
            return MarketHeatContext.default(region, project_type)

    def _compute(self, region: str, project_type: str) -> MarketHeatContext:
        """
        Internal computation. Raises on invalid data (caller catches and degrades).
        """
        # ── Step 1: Subquery of eligible tenders ─────────────────────────────
        # Only closed tenders with revealed winning prices
        tenders_subq = (
            select(HistoricalTender.id)
            .where(
                HistoricalTender.region == region,
                HistoricalTender.project_type == project_type,
                HistoricalTender.tender_status == 'closed',
                HistoricalTender.price_revealed == True,  # noqa: E712
                HistoricalTender.winning_price.isnot(None),
            )
            .subquery()
        )

        # ── Step 2: Tender-level discount rate stats ──────────────────────────
        # NULLIF prevents division-by-zero when budget_amount=0
        discount_expr = func.coalesce(
            func.nullif(HistoricalTender.winning_price / func.nullif(HistoricalTender.budget_amount, 0), 0),
            None
        )

        tender_stats = self.db.execute(
            select(
                func.count(HistoricalTender.id).label('count'),
                func.avg(discount_expr).label('avg_discount_rate'),
                func.median(discount_expr).label('median_discount_rate'),
            )
            .where(HistoricalTender.id.in_(select(tenders_subq)))
        ).fetchone()

        tender_count = tender_stats.count if tender_stats and tender_stats.count else 0

        # ── Step 3: Our bid outcome stats ─────────────────────────────────────
        bid_stats = self.db.execute(
            select(
                func.count(HistoricalBid.id).label('bid_count'),
                func.avg(HistoricalBid.total_bidders_count).label('bidder_count_avg'),
                func.median(HistoricalBid.total_bidders_count).label('bidder_count_median'),
                func.avg(HistoricalBid.price_gap_percentage).label('avg_price_gap_pct'),
                # Win count: SUM of (our_bid_status == 'won' ? 1 : 0)
                func.sum(
                    case(
                        (HistoricalBid.our_bid_status == 'won', 1),
                        else_=0,
                    )
                ).label('win_count'),
            )
            .where(HistoricalBid.historical_tender_id.in_(select(tenders_subq)))
        ).fetchone()

        bid_count = bid_stats.bid_count if bid_stats and bid_stats.bid_count else 0
        win_count = bid_stats.win_count if bid_stats and bid_stats.win_count else 0

        # ── Step 4: Price gap bucket distribution ─────────────────────────────
        bucket_rows = self.db.execute(
            select(
                HistoricalBid.price_gap_bucket,
                func.count(HistoricalBid.id).label('cnt'),
            )
            .where(HistoricalBid.historical_tender_id.in_(select(tenders_subq)))
            .where(HistoricalBid.price_gap_bucket.isnot(None))
            .group_by(HistoricalBid.price_gap_bucket)
        ).fetchall()

        bucket_distribution = {row.price_gap_bucket: row.cnt for row in bucket_rows} if bucket_rows else {}

        # ── Step 5: Safe arithmetic — never raise on empty data ───────────────
        avg_discount = _safe_float(tender_stats.avg_discount_rate) if tender_stats else None

        # expected_competitive_price is stored as a Decimal discount multiplier
        expected_competitive_price = None
        if avg_discount is not None and tender_count > 0:
            # Clamp discount rate to [0.01, 1.5] to prevent absurd values
            clamped = max(0.01, min(1.5, avg_discount))
            expected_competitive_price = Decimal(str(round(clamped, 4)))

        win_rate = None
        if bid_count > 0:
            win_rate = float(win_count) / float(bid_count)

        return MarketHeatContext(
            region=region,
            project_type=project_type,
            avg_discount_rate=avg_discount,
            median_discount_rate=_safe_float(tender_stats.median_discount_rate) if tender_stats else None,
            bidder_count_avg=_safe_float(bid_stats.bidder_count_avg) if bid_stats else None,
            bidder_count_median=_safe_float(bid_stats.bidder_count_median) if bid_stats else None,
            expected_competitive_price=expected_competitive_price,
            historical_win_rate=win_rate,
            sample_size=bid_count,
            avg_price_gap_pct=_safe_float(bid_stats.avg_price_gap_pct) if bid_stats else None,
            price_gap_bucket_distribution=bucket_distribution,
        )


# ─── Safe arithmetic helpers ──────────────────────────────────────────────────


def _safe_float(value, default: Optional[float] = None) -> Optional[float]:
    """Convert to float, returning default if None or NaN."""
    if value is None:
        return default
    try:
        f = float(value)
        return f if f == f else default  # NaN guard
    except (ValueError, TypeError):
        return default
