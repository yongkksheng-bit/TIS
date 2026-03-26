"""BidReviewEngine — analyzes bid outcomes and feeds the knowledge base."""
import json
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.project import Project
from app.models.pricing import PricingDecision, PriceHistory, CostEstimate
from app.models.tech_proposal import TechProposalTask
from app.models.formal_review import FormalReviewItem
from app.models.review import BidOutcome, WinningDNA, DisqualificationTrap, KnowledgeEvolutionLog
from app.models.knowledge_chunk import KnowledgeChunk


class BidReviewEngine:
    """
    Analyzes bid outcomes (win/lose/disqualification) and updates the knowledge base.

    Called after a bid outcome is determined to:
    - Extract winning DNA from successful bids
    - Record price history for cold-start modeling
    - Build disqualification trap library
    - Log knowledge evolution events
    """

    def __init__(self, db: Session, project_id: int):
        self.db = db
        self.project_id = project_id

        # Lazy-loaded
        self._project: Optional[Project] = None
        self._pricing_decision: Optional[PricingDecision] = None
        self._tech_proposal: Optional[TechProposalTask] = None
        self._existing_outcome: Optional[BidOutcome] = None

    def log_outcome(
        self,
        is_win: bool,
        competitor_price: Optional[float],
        feedback: str,
        outcome_status: str,
    ) -> dict:
        """
        Log a bid outcome and update knowledge base.

        Args:
            is_win: Whether we won the bid
            competitor_price: Winning competitor's price (if known)
            feedback: Human-readable feedback or disqualification reason
            outcome_status: 'win', 'lose', or 'disqualified'

        Returns:
            dict with outcome details

        Raises:
            ValueError: If project not found
        """
        # Step 1: Load project
        self._project = self.db.get(Project, self.project_id)
        if self._project is None:
            raise ValueError("Project not found")

        # Step 2: Load pricing decision (latest decided)
        self._pricing_decision = (
            self.db.query(PricingDecision)
            .filter(
                PricingDecision.project_id == self.project_id,
                PricingDecision.status == "decided",
            )
            .order_by(PricingDecision.id.desc())
            .first()
        )

        # Step 3: Load existing bid_outcome (if any)
        self._existing_outcome = (
            self.db.query(BidOutcome)
            .filter(BidOutcome.project_id == self.project_id)
            .order_by(desc(BidOutcome.id))
            .first()
        )

        # Delegate to specific handler
        if outcome_status == "win" or is_win:
            return self._handle_win(competitor_price, feedback)
        elif outcome_status == "disqualified":
            return self._handle_disqualified(competitor_price, feedback)
        elif outcome_status == "lose":
            return self._handle_lose(competitor_price, feedback)
        else:
            raise ValueError(f"Unknown outcome_status: {outcome_status}")

    def get_analysis(self) -> dict:
        """
        Get analysis of the current bid outcome.

        Returns:
            dict with analysis details
        """
        if self._project is None:
            self._project = self.db.get(Project, self.project_id)

        outcome = (
            self.db.query(BidOutcome)
            .filter(BidOutcome.project_id == self.project_id)
            .order_by(desc(BidOutcome.id))
            .first()
        )

        return {
            "project_id": self.project_id,
            "outcome_status": outcome.outcome_status if outcome else None,
            "analysis_type": outcome.outcome_status if outcome else None,
            "is_manual_error": outcome.is_manual_error if outcome else False,
        }

    def _handle_win(self, competitor_price: Optional[float], feedback: str) -> dict:
        """Handle win outcome."""
        if self._pricing_decision is None:
            raise ValueError("Pricing decision not found for win outcome")

        # Step 1: Calculate discount_rate
        boss_final_price = self._pricing_decision.boss_final_price
        cost_base = self._pricing_decision.cost_base
        budget_limit = self._pricing_decision.budget_limit or Decimal("0")

        if budget_limit > 0:
            discount_rate = (boss_final_price - cost_base) / budget_limit
        else:
            discount_rate = Decimal("0")

        # Step 2: Determine strategy_type
        strategy_type = "aggressive" if discount_rate < Decimal("0.05") else "balanced"

        # Step 3: Insert into PriceHistory
        price_history = PriceHistory(
            project_type=self._project.project_type,
            region=self._project.region,
            budget_amount=budget_limit,
            our_cost=cost_base,
            our_bid_price=boss_final_price,
            winning_price=Decimal(str(competitor_price)) if competitor_price else None,
            discount_rate=discount_rate,
            bid_date=date.today(),
            is_our_win=True,
            data_source="bid_review",
        )
        self.db.add(price_history)
        self.db.flush()  # Get price_history.id

        # Step 4: Load confirmed tech proposal
        self._tech_proposal = (
            self.db.query(TechProposalTask)
            .filter(
                TechProposalTask.project_id == self.project_id,
                TechProposalTask.status == "confirmed",
            )
            .first()
        )

        dna_count = 0
        price_history_id = price_history.id

        if self._tech_proposal and self._tech_proposal.generated_content:
            # Step 5: Parse generated_content and extract sections
            content = self._tech_proposal.generated_content
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except json.JSONDecodeError:
                    content = {}
            elif not isinstance(content, dict):
                content = {}

            sections = content.get("sections", []) if isinstance(content, dict) else []
            if isinstance(sections, list):
                # Step 6: Create WinningDNA for each section
                for section in sections:
                    section_title = section.get("title") or section.get("section_title", "Unknown")
                    dna = WinningDNA(
                        project_id=self.project_id,
                        dna_type="high_score_response",
                        score_contribution=8,  # default assumption since we won
                        scoring_item_matched=section_title,
                        reused_in_projects="[]",
                        reuse_success_rate=None,
                    )
                    self.db.add(dna)
                    dna_count += 1

        # Step 7: Insert KnowledgeEvolutionLog for each DNA chunk
        if dna_count > 0:
            # Get knowledge chunks for this project
            chunks = (
                self.db.query(KnowledgeChunk)
                .filter(KnowledgeChunk.source_project_id == self.project_id)
                .all()
            )
            for chunk in chunks:
                log = KnowledgeEvolutionLog(
                    chunk_id=chunk.id,
                    action_type="confirmed_win",
                    project_id=self.project_id,
                    old_quality_score=chunk.chunk_metadata.get("quality_score") if chunk.chunk_metadata else None,
                    new_quality_score=20,  # +20 quality score per spec
                    reason=f"Won project {self.project_id}, +20 quality score",
                )
                self.db.add(log)
        else:
            # Even without DNA, log the win event
            chunks = (
                self.db.query(KnowledgeChunk)
                .filter(KnowledgeChunk.source_project_id == self.project_id)
                .all()
            )
            for chunk in chunks:
                log = KnowledgeEvolutionLog(
                    chunk_id=chunk.id,
                    action_type="confirmed_win",
                    project_id=self.project_id,
                    reason=f"Won project {self.project_id}, +20 quality score",
                )
                self.db.add(log)

        # Create bid outcome record
        bid_outcome = BidOutcome(
            project_id=self.project_id,
            outcome_status="win",
            outcome_date=date.today(),
            final_bid_price=float(boss_final_price),
            winning_price=competitor_price,
            is_manual_error=False,
            reviewed_at=datetime.now(timezone.utc),
        )
        self.db.add(bid_outcome)
        self.db.commit()

        return {
            "outcome_type": "win",
            "dna_count": dna_count,
            "price_history_id": price_history_id,
        }

    def _handle_disqualified(self, competitor_price: Optional[float], feedback: str) -> dict:
        """Handle disqualification outcome."""
        # Step 1: Create BidOutcome with is_manual_error=False initially
        bid_outcome = BidOutcome(
            project_id=self.project_id,
            outcome_status="disqualified",
            outcome_date=date.today(),
            final_bid_price=float(self._pricing_decision.boss_final_price) if self._pricing_decision else 0.0,
            disqualification_reason=feedback,
            disqualification_type="fatal_formal",  # default type
            is_manual_error=False,
            reviewed_at=datetime.now(timezone.utc),
        )
        self.db.add(bid_outcome)
        self.db.flush()

        # Step 2: Detect manual error from FormalReviewItem
        manual_error_item = (
            self.db.query(FormalReviewItem)
            .filter(
                FormalReviewItem.project_id == self.project_id,
                FormalReviewItem.specialist_status == "deleted",
                FormalReviewItem.risk_level == "fatal",
            )
            .first()
        )

        is_manual_error = manual_error_item is not None
        if is_manual_error:
            bid_outcome.is_manual_error = True
            bid_outcome.disqualification_reason = feedback or "Manual error detected in formal review"

        # Step 3: Upsert DisqualificationTrap
        trap_title = feedback[:255] if feedback else "Unknown disqualification"
        trap_category = bid_outcome.disqualification_type or "format"

        # Check if trap with same title exists
        existing_trap = (
            self.db.query(DisqualificationTrap)
            .filter(DisqualificationTrap.trap_title == trap_title)
            .first()
        )

        if existing_trap:
            # Increment occurrence count
            existing_trap.occurrence_count += 1
            trap_id = existing_trap.id
        else:
            # Create new trap
            trap_code = f"TRAP_{trap_category}_{bid_outcome.id}"
            trap = DisqualificationTrap(
                trap_code=trap_code,
                trap_category=trap_category,
                trap_title=trap_title,
                trap_description=feedback,
                first_occurrence_project_id=self.project_id,
                occurrence_count=1,
                is_active=True,
            )
            self.db.add(trap)
            self.db.flush()
            trap_id = trap.id

        # Step 4: Insert KnowledgeEvolutionLog
        chunks = (
            self.db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.source_project_id == self.project_id)
            .all()
        )
        for chunk in chunks:
            log = KnowledgeEvolutionLog(
                chunk_id=chunk.id,
                action_type="confirmed_lose",
                project_id=self.project_id,
                reason=f"Lost/disqualified project {self.project_id}: {feedback}",
            )
            self.db.add(log)

        self.db.commit()

        return {
            "outcome_type": "disqualification",
            "trap_id": trap_id,
            "is_manual_error": is_manual_error,
        }

    def _handle_lose(self, competitor_price: Optional[float], feedback: str) -> dict:
        """Handle lose outcome."""
        # Step 1: Create BidOutcome record
        bid_outcome = BidOutcome(
            project_id=self.project_id,
            outcome_status="lose",
            outcome_date=date.today(),
            final_bid_price=float(self._pricing_decision.boss_final_price) if self._pricing_decision else 0.0,
            winning_price=competitor_price,
            is_manual_error=False,
            reviewed_at=datetime.now(timezone.utc),
        )
        self.db.add(bid_outcome)

        # Step 2: Record to price_history if competitor_price provided
        price_history_id = None
        if competitor_price is not None and self._pricing_decision:
            boss_final_price = self._pricing_decision.boss_final_price
            cost_base = self._pricing_decision.cost_base
            budget_limit = self._pricing_decision.budget_limit or Decimal("0")

            if budget_limit > 0:
                discount_rate = (boss_final_price - cost_base) / budget_limit
            else:
                discount_rate = Decimal("0")

            price_history = PriceHistory(
                project_type=self._project.project_type,
                region=self._project.region,
                budget_amount=budget_limit,
                our_cost=cost_base,
                our_bid_price=boss_final_price,
                winning_price=Decimal(str(competitor_price)),
                discount_rate=discount_rate,
                bid_date=date.today(),
                is_our_win=False,
                data_source="bid_review",
            )
            self.db.add(price_history)
            self.db.flush()
            price_history_id = price_history.id

        # Step 3: Insert KnowledgeEvolutionLog
        chunks = (
            self.db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.source_project_id == self.project_id)
            .all()
        )
        for chunk in chunks:
            log = KnowledgeEvolutionLog(
                chunk_id=chunk.id,
                action_type="confirmed_lose",
                project_id=self.project_id,
                reason=f"Lost project {self.project_id} to competitor at {competitor_price}",
            )
            self.db.add(log)

        self.db.commit()

        return {
            "outcome_type": "lose",
            "competitor_price": competitor_price,
        }
