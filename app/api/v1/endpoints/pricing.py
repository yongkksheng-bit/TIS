"""Week 4 Pricing API endpoints — cost estimation, game theory, and pricing decisions."""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.project import Project
from app.models.pricing import CostEstimate, PricingDecision
from app.core.week4_pricing.cost_engine import CostEstimationEngine
from app.core.week4_pricing.game_theory import PricingGameTheoryModel
from app.core.week4_pricing.intercept_rules import PricingInterceptRules
from app.schemas.week4 import (
    CostEstimateCreate,
    CostEstimateResponse,
    PriceScenario,
    PricingCalculationResponse,
    PricingDecisionCreate,
    PricingDecisionResponse,
    PricingDashboardResponse,
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
    """Get pricing dashboard: cost baseline + A/B/C scenarios."""
    project = _get_project_or_404(db, project_id)
    confirmed = _get_confirmed_cost(db, project_id)

    budget = Decimal(str(project.budget_amount)) if project.budget_amount else None

    if confirmed:
        game_model = PricingGameTheoryModel(
            cost=confirmed.total_cost,
            budget=budget or Decimal('999999999'),
        )
        scenarios = game_model.generate_price_scenarios()
    else:
        scenarios = []

    return ResponseWrapper(data={
        "project_id": project_id,
        "cost_base": float(confirmed.total_cost) if confirmed else None,
        "budget_limit": float(budget) if budget else None,
        "scenarios": [PriceScenario(**s).model_dump() for s in scenarios],
    })