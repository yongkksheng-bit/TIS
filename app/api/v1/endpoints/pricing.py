"""Week 4 Pricing API endpoints — cost estimation, game theory, and pricing decisions."""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.project import Project
from app.models.pricing import CostEstimate, PricingDecision
from app.models.enums import ProjectStatus
from app.core.week4_pricing.cost_engine import CostEstimationEngine
from app.core.week4_pricing.game_theory import PricingGameTheoryModel
from app.core.week4_pricing.intercept_rules import PricingInterceptRules
from app.core.week4_pricing.price_benchmark import PriceBenchmarkCache
from app.schemas.week4 import (
    CostEstimateCreate,
    CostEstimateResponse,
    ConfirmedCostEstimateResponse,
    PriceScenario,
    PricingCalculationResponse,
    PricingDecisionCreate,
    PricingDecisionUpsertRequest,
    PricingDecisionResponse,
    PricingDashboardResponse,
    MarketBenchmarkData,
)
from app.schemas.common import ResponseWrapper


router = APIRouter(prefix="/api/v1", tags=["pricing"])


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return project


def _get_confirmed_cost(db: Session, project_id: int) -> CostEstimate:
    """Get the latest confirmed cost estimate for a project."""
    return (
        db.query(CostEstimate)
        .filter_by(project_id=project_id, is_confirmed=True)
        .order_by(CostEstimate.version_number.desc())
        .first()
    )


# ─── POST /projects/{project_id}/cost-estimates ───────────────────────────

@router.post("/projects/{project_id}/cost-estimates")
def create_cost_estimate(
    project_id: int,
    data: CostEstimateCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new cost estimate version for a project.
    Any user (specialist/finance/boss) can submit.
    New version = latest_version + 1.
    """
    project = _get_project_or_404(db, project_id)

    # Get next version number
    latest = (
        db.query(CostEstimate)
        .filter_by(project_id=project_id)
        .order_by(CostEstimate.version_number.desc())
        .first()
    )
    version = (latest.version_number + 1) if latest else 1

    # Compute total
    total = (
        data.food_cost + data.logistics_cost +
        data.labor_cost + data.management_cost + data.other_cost
    )

    estimate = CostEstimate(
        project_id=project_id,
        version_number=version,
        food_cost=data.food_cost,
        logistics_cost=data.logistics_cost,
        labor_cost=data.labor_cost,
        management_cost=data.management_cost,
        other_cost=data.other_cost,
        total_cost=total,
        estimated_by=1,  # TODO: from auth context
        estimate_reason=data.estimate_reason,
        is_confirmed=False,
    )
    db.add(estimate)
    db.commit()

    engine = CostEstimationEngine()
    breakdown = engine.breakdown_cost(total)

    return ResponseWrapper(data={
        "id": estimate.id,
        "version_number": version,
        "total_cost": float(total),
        "breakdown": {k: float(v) for k, v in breakdown.items()},
        "estimated_by": 1,
        "is_confirmed": False,
    })


# ─── POST /cost-estimates/{estimate_id}/confirm ───────────────────────────

@router.post("/cost-estimates/{estimate_id}/confirm")
def confirm_cost_estimate(estimate_id: int, db: Session = Depends(get_db)):
    """Mark a cost estimate as the confirmed baseline for pricing."""
    estimate = db.get(CostEstimate, estimate_id)
    if not estimate:
        raise HTTPException(status_code=404, detail="CostEstimate not found")
    estimate.is_confirmed = True
    db.commit()
    return ResponseWrapper(data={"id": estimate_id, "is_confirmed": True})


# ─── GET /projects/{project_id}/cost-estimates/current ──────────────────

@router.get("/projects/{project_id}/cost-estimates/current")
def get_confirmed_cost_estimate(project_id: int, db: Session = Depends(get_db)):
    """
    Get the currently confirmed cost estimate with full breakdown for a project.
    Returns 404 if no confirmed estimate exists yet.
    """
    _get_project_or_404(db, project_id)
    confirmed = _get_confirmed_cost(db, project_id)
    if not confirmed:
        raise HTTPException(status_code=404, detail="No confirmed cost estimate found")
    return ResponseWrapper(data=ConfirmedCostEstimateResponse.model_validate(confirmed).model_dump())


# ─── POST /projects/{project_id}/pricing-calculations ─────────────────────

@router.post("/projects/{project_id}/pricing-calculations")
def calculate_pricing(project_id: int, db: Session = Depends(get_db)):
    """
    Generate A/B/C price scenarios using game theory model.
    Requires a confirmed cost estimate to exist.
    """
    project = _get_project_or_404(db, project_id)
    confirmed = _get_confirmed_cost(db, project_id)

    if not confirmed:
        raise HTTPException(
            status_code=400,
            detail="No confirmed cost estimate. Please create and confirm a cost estimate first.",
        )

    budget = Decimal(str(project.budget_amount)) if project.budget_amount else Decimal('999999999')
    relationship_index = 100 if project.relationship_flag else 0

    model = PricingGameTheoryModel(
        cost=confirmed.total_cost,
        budget=budget,
        price_score_weight=Decimal('0.3'),
        relationship_index=relationship_index,
    )

    scenarios = model.generate_price_scenarios()
    optimal = next(s for s in scenarios if s.get('is_recommended'))

    return ResponseWrapper(data={
        "project_id": project_id,
        "cost_base": float(confirmed.total_cost),
        "budget_limit": float(budget) if project.budget_amount else None,
        "scenarios": [PriceScenario(**s).model_dump() for s in scenarios],
        "optimal_recommendation": PriceScenario(**optimal).model_dump(),
    })


# ─── POST /projects/{project_id}/pricing-decisions ────────────────────────

@router.post("/projects/{project_id}/pricing-decisions")
def submit_pricing_decision(
    project_id: int,
    data: PricingDecisionCreate,
    db: Session = Depends(get_db),
):
    """
    Submit a boss final pricing decision.
    Enforces intercept rules:
      - Loss pricing → 400 error
      - Over limit → 400 error (requires confirm_override param)
      - Deviation >5% → requires detailed reason
    """
    project = _get_project_or_404(db, project_id)

    # Guard: only accept pricing in valid states
    VALID_PRICING_STATES = {ProjectStatus.APPROVED_BY_SPECIALIST.value, ProjectStatus.AWAITING_PRICING.value}
    if project.status not in VALID_PRICING_STATES:
        raise HTTPException(
            status_code=400,
            detail=f"无法在状态 '{project.status}' 下提交定价决策（仅在'待定价'或'专家已审批'状态下可提交）",
        )

    confirmed = _get_confirmed_cost(db, project_id)

    if not confirmed:
        raise HTTPException(
            status_code=400,
            detail="No confirmed cost estimate",
        )

    budget = Decimal(str(project.budget_amount)) if project.budget_amount else None

    # Intercept rules
    rules = PricingInterceptRules()

    # Rule 1: cost vs budget warning (non-blocking)
    if budget:
        cost_check = rules.check_cost_vs_budget(confirmed.total_cost, budget)
        # Warning only — proceed

    # Rule 2: loss pricing (blocking)
    price_check = rules.check_final_price(
        final_price=data.boss_final_price,
        total_cost=confirmed.total_cost,
        budget_limit=budget,
        system_optimal=None,  # Will check deviation after we compute optimal
    )
    if price_check.level == 'error':
        raise HTTPException(status_code=400, detail=price_check.message)
    if price_check.requires_confirmation:
        raise HTTPException(status_code=400, detail=price_check.message)

    # Rule 4: deviation > 5% — compute system optimal and check
    game_model = PricingGameTheoryModel(
        cost=confirmed.total_cost,
        budget=budget or Decimal('999999999'),
    )
    scenarios = game_model.generate_price_scenarios()
    optimal = next(s for s in scenarios if s.get('is_recommended'))
    system_optimal = Decimal(str(optimal['price']))

    deviation_check = rules.check_deviation(data.boss_final_price, system_optimal)
    if deviation_check.requires_reason and len(data.boss_decision_reason.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail=f"定价差异{float(deviation_check.deviation_pct):.1%}，请详细说明原因（至少10字）",
        )

    # Compute deviation percentage
    deviation = abs(data.boss_final_price - system_optimal) / system_optimal
    is_under_limit = bool(budget and data.boss_final_price <= budget)

    decision = PricingDecision(
        project_id=project_id,
        cost_estimate_id=confirmed.id,
        cost_base=confirmed.total_cost,
        system_suggested_low=confirmed.total_cost * Decimal('1.02'),
        system_suggested_high=confirmed.total_cost * Decimal('1.15'),
        system_suggested_optimal=system_optimal,
        finance_suggested_price=data.finance_suggested_price,
        boss_final_price=data.boss_final_price,
        boss_decision_reason=data.boss_decision_reason,
        deviation_from_system=deviation,
        deviation_reason_category=data.deviation_reason_category,
        budget_limit=budget,
        is_under_limit=is_under_limit,
        status='decided',
    )
    db.add(decision)
    # Advance project to Week 5 formal review (single atomic commit)
    project.status = ProjectStatus.AWAITING_REVIEW.value
    db.commit()

    return ResponseWrapper(data={
        "id": decision.id,
        "project_id": project_id,
        "boss_final_price": float(data.boss_final_price),
        "status": decision.status,
        "deviation_from_system": float(deviation),
    })


# ─── GET /projects/{project_id}/pricing-dashboard ───────────────────────

@router.get("/projects/{project_id}/pricing-dashboard")
def get_pricing_dashboard(project_id: int, db: Session = Depends(get_db)):
    """
    Get pricing dashboard: cost baseline + A/B/C scenarios + market benchmark.

    Phase 2 upgrade: attaches historical market benchmark data
    (avg discount rate, expected competitive price, win rate) from historical_tenders
    and passes it to the game theory model to anchor scenarios to market equilibrium.

    Graceful degradation: if historical data is unavailable or query fails,
    market_benchmark is null and game theory falls back to cost-plus scenarios.
    """
    project = _get_project_or_404(db, project_id)
    confirmed = _get_confirmed_cost(db, project_id)

    budget = Decimal(str(project.budget_amount)) if project.budget_amount else None

    # ── Step 1: Compute market benchmark (hard-isolated historical data) ────
    market_context = None
    benchmark_data = None
    try:
        region = project.region or "未知地区"
        project_type = project.project_type or "service"
        cache = PriceBenchmarkCache(db)
        market_context = cache.get_market_context(region, project_type)
        if market_context.has_data:
            # Compute expected_competitive_price in Yuan (budget * discount_rate)
            eq_price_float = None
            if market_context.expected_competitive_price is not None and budget:
                eq_price_float = float(market_context.expected_competitive_price * budget)
            benchmark_data = MarketBenchmarkData(
                region=region,
                project_type=project_type,
                avg_discount_rate=market_context.avg_discount_rate,
                median_discount_rate=market_context.median_discount_rate,
                bidder_count_avg=market_context.bidder_count_avg,
                bidder_count_median=market_context.bidder_count_median,
                expected_competitive_price=eq_price_float,
                historical_win_rate=market_context.historical_win_rate,
                sample_size=market_context.sample_size,
                avg_price_gap_pct=market_context.avg_price_gap_pct,
                price_gap_bucket_distribution=market_context.price_gap_bucket_distribution,
                has_data=True,
            )
    except Exception:
        # Graceful degradation: DB errors → null benchmark, no disruption
        benchmark_data = None

    # ── Step 2: Generate scenarios (with or without market context) ──────────
    if confirmed:
        game_model = PricingGameTheoryModel(
            cost=confirmed.total_cost,
            budget=budget or Decimal('999999999'),
            market_context=market_context,
        )
        scenarios = game_model.generate_price_scenarios()
    else:
        scenarios = []

    return ResponseWrapper(data=PricingDashboardResponse(
        project_id=project_id,
        cost_base=confirmed.total_cost if confirmed else None,
        budget_limit=budget,
        scenarios=[PriceScenario(**s) for s in scenarios],
        market_benchmark=benchmark_data,
    ).model_dump())


# ─── PUT /projects/{project_id}/pricing-decisions (upsert) ───────────────────

@router.put("/projects/{project_id}/pricing-decisions")
def upsert_pricing_decision(
    project_id: int,
    data: PricingDecisionUpsertRequest,
    db: Session = Depends(get_db),
):
    """
    Unified upsert for pricing decisions.

    action_type:
      - specialist_draft: Specialist saves proposed price (no status change)
      - submit_to_boss:  Specialist requests boss decision → project status = pending_boss_approval
      - boss_final:       Boss confirms final price → project status = formal_review

    Unlimited overwrites allowed while project is in pricing stage.
    """
    project = _get_project_or_404(db, project_id)

    # Only allow upsert before formal_review
    if project.status == ProjectStatus.AWAITING_REVIEW.value:
        raise HTTPException(
            status_code=400,
            detail="项目已处于正式评审阶段，定价不可再修改",
        )

    confirmed = _get_confirmed_cost(db, project_id)
    budget = Decimal(str(project.budget_amount)) if project.budget_amount else None

    # Upsert existing or create new
    existing = (
        db.query(PricingDecision)
        .filter_by(project_id=project_id)
        .order_by(PricingDecision.id.desc())
        .first()
    )

    if existing:
        decision = existing
    else:
        # Need cost_base to create — require confirmed estimate first
        if not confirmed:
            raise HTTPException(
                status_code=400,
                detail="请先创建并确认成本估算，再进行定价",
            )
        decision = PricingDecision(
            project_id=project_id,
            cost_estimate_id=confirmed.id,
            cost_base=confirmed.total_cost,
            system_suggested_low=confirmed.total_cost * Decimal('1.02'),
            system_suggested_high=confirmed.total_cost * Decimal('1.15'),
            budget_limit=budget,
            status='draft',
        )
        db.add(decision)
        db.flush()

    # Compute system optimal for deviation tracking
    system_optimal = None
    if confirmed:
        game_model = PricingGameTheoryModel(
            cost=confirmed.total_cost,
            budget=budget or Decimal('999999999'),
        )
        scenarios = game_model.generate_price_scenarios()
        optimal = next((s for s in scenarios if s.get('is_recommended')), None)
        if optimal:
            system_optimal = Decimal(str(optimal['price']))

    # Dispatch by action_type
    new_status = project.status
    deviation = None

    if data.action_type == 'specialist_draft':
        decision.specialist_price = data.price
        decision.specialist_notes = data.notes
        decision.action_type = 'specialist_draft'
        if project.status == ProjectStatus.UPLOADED.value:
            new_status = ProjectStatus.AWAITING_PRICING.value

    elif data.action_type == 'submit_to_boss':
        decision.specialist_price = data.price
        decision.specialist_notes = data.notes
        decision.action_type = 'submit_to_boss'
        new_status = ProjectStatus.PENDING_BOSS_APPROVAL.value

    elif data.action_type == 'boss_final':
        decision.boss_final_price = data.price
        decision.boss_decision_reason = data.notes or ''
        decision.action_type = 'boss_final'
        if system_optimal:
            deviation = abs(data.price - system_optimal) / system_optimal
            decision.deviation_from_system = deviation
        decision.status = 'decided'
        new_status = ProjectStatus.AWAITING_REVIEW.value
        if budget:
            decision.is_under_limit = data.price <= budget

    project.status = new_status
    db.commit()

    # Compute deviation for response
    if system_optimal and data.price:
        deviation = abs(data.price - system_optimal) / system_optimal

    return ResponseWrapper(data={
        "id": decision.id,
        "project_id": project_id,
        "specialist_price": float(decision.specialist_price) if decision.specialist_price else None,
        "boss_final_price": float(decision.boss_final_price) if decision.boss_final_price else None,
        "status": decision.status,
        "action_type": decision.action_type,
        "deviation_from_system": float(deviation) if deviation else None,
        "new_project_status": new_status,
    })