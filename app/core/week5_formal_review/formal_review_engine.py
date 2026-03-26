"""FormalReviewEngine — auto-generates formal review checklist items.

Called after PricingDecision is confirmed to gate final bid document generation.
"""
from datetime import date, timedelta
from typing import Optional
from sqlalchemy.orm import Session


class FormalReviewEngine:
    """
    Orchestrates formal review checklist generation.

    Loads data from Week 1 (OCR qualifications), Week 3 (tech proposals),
    and Week 4 (pricing decisions) to build a structured checklist of
    risk items that must be resolved before final bid generation.
    """

    def __init__(self, db: Session, project_id: int):
        self.db = db
        self.project_id = project_id

        # Lazy-loaded in methods to avoid circular imports
        self._project: Optional[object] = None
        self._tender: Optional[object] = None
        self._qualifications: list = []
        self._pricing_decision: Optional[object] = None
        self._tech_proposal: Optional[object] = None

    # ─── Public API ────────────────────────────────────────────────────────────

    def generate_review_checklist(self) -> list[dict]:
        """
        Generate the full formal review checklist.

        Runs all check methods in order, collects their items, and bulk-inserts
        into the database before returning.

        Returns:
            list[dict]: checklist item dicts with keys:
                source_type, check_category, check_title, check_description,
                reference_clause, system_status, risk_level, project_id
        """
        from app.models.formal_review import FormalReviewItem  # noqa: F401

        checklist: list[dict] = []

        # 1. Qualification validity checks
        checklist.extend(self._check_qualification_validity())

        # 2. Price compliance checks
        checklist.extend(self._check_price_compliance())

        # 3. Document integrity checks
        checklist.extend(self._check_document_integrity())

        # 4. Signature/seal stub
        checklist.extend(self._check_signature_seal())

        # 5. Seal requirements stub
        checklist.extend(self._check_seal_requirements())

        # Bulk insert all items
        for item in checklist:
            db_item = FormalReviewItem(
                project_id=self.project_id,
                source_type=item.get('source_type', 'system_parsed'),
                check_category=item['check_category'],
                check_title=item['check_title'],
                check_description=item.get('check_description', ''),
                reference_clause=item.get('reference_clause'),
                system_status=item['system_status'],
                risk_level=item['risk_level'],
                specialist_status='pending',
            )
            self.db.add(db_item)

        if checklist:
            self.db.commit()

        return checklist

    # ─── Private: Loaders ──────────────────────────────────────────────────────

    def _load_project(self):
        """Load project from database."""
        if self._project is None:
            from app.models.project import Project  # noqa: F401
            self._project = self.db.get(Project, self.project_id)
        return self._project

    def _load_tender(self):
        """Load tender document for the project."""
        if self._tender is None:
            from app.models.document import TenderDocument  # noqa: F401
            result = (
                self.db.query(TenderDocument)
                .filter(TenderDocument.project_id == self.project_id)
                .first()
            )
            self._tender = result
        return self._tender

    def _load_qualifications(self) -> list:
        """
        Load OCR extractions with standard_cert_id (qualification certs).

        Returns:
            list of OcrExtraction objects
        """
        if not self._qualifications:
            from app.models.ocr import OcrExtraction  # noqa: F401
            self._qualifications = (
                self.db.query(OcrExtraction)
                .filter(
                    OcrExtraction.project_id == self.project_id,
                    OcrExtraction.standard_cert_id.isnot(None),
                )
                .all()
            )
        return self._qualifications

    def _load_pricing_decision(self):
        """Load latest confirmed pricing decision."""
        if self._pricing_decision is None:
            from app.models.pricing import PricingDecision  # noqa: F401
            result = (
                self.db.query(PricingDecision)
                .filter(
                    PricingDecision.project_id == self.project_id,
                    PricingDecision.status == 'decided',
                )
                .order_by(PricingDecision.id.desc())
                .first()
            )
            self._pricing_decision = result
        return self._pricing_decision

    def _load_tech_proposal(self):
        """Load confirmed tech proposal task."""
        if self._tech_proposal is None:
            from app.models.tech_proposal import TechProposalTask  # noqa: F401
            result = (
                self.db.query(TechProposalTask)
                .filter(
                    TechProposalTask.project_id == self.project_id,
                    TechProposalTask.status == 'confirmed',
                )
                .first()
            )
            self._tech_proposal = result
        return self._tech_proposal

    # ─── Private: Check Methods ───────────────────────────────────────────────

    def _check_qualification_validity(self) -> list[dict]:
        """
        Check each OCR qualification certificate against bid open date.

        Rules:
        - valid_until < bid_open_date        → risk='fatal',   status='failed'
        - valid_until < bid_open_date + 90d  → risk='warning', status='warning'
        - otherwise                          → risk='info',    status='passed'
        """
        qualifications = self._load_qualifications()
        project = self._load_project()

        if not project:
            return []

        bid_open_date: date = project.bid_open_date
        if not bid_open_date:
            return []

        checklist: list[dict] = []
        warning_threshold = bid_open_date + timedelta(days=90)

        for qual in qualifications:
            valid_until = qual.valid_until
            if not valid_until:
                continue

            # Normalize to date in case datetime is passed
            if hasattr(valid_until, 'date'):
                valid_until = valid_until.date()

            cert_name = qual.normalized_value or f"Certificate #{qual.id}"
            days_until_expiry = (valid_until - bid_open_date).days

            if valid_until < bid_open_date:
                # Expired before bid opening
                checklist.append({
                    'source_type': 'ocr_comparison',
                    'check_category': 'qualification_validity',
                    'check_title': f"{cert_name} 有效期检查",
                    'check_description': (
                        f"{cert_name} 有效期至 {valid_until}，"
                        f"开标日期 {bid_open_date}，已过期"
                    ),
                    'reference_clause': '招标文件资质要求部分',
                    'system_status': 'failed',
                    'risk_level': 'fatal',
                })
            elif valid_until < warning_threshold:
                # Expiring soon (within 90 days of bid open)
                checklist.append({
                    'source_type': 'ocr_comparison',
                    'check_category': 'qualification_validity',
                    'check_title': f"{cert_name} 有效期检查",
                    'check_description': (
                        f"{cert_name} 有效期至 {valid_until}，"
                        f"距开标日 {days_until_expiry} 天，建议在标书中承诺到期前更新"
                    ),
                    'reference_clause': '招标文件资质要求部分',
                    'system_status': 'warning',
                    'risk_level': 'warning',
                })
            else:
                # Valid
                checklist.append({
                    'source_type': 'ocr_comparison',
                    'check_category': 'qualification_validity',
                    'check_title': f"{cert_name} 有效期检查",
                    'check_description': f"{cert_name} 有效期正常（至 {valid_until}）",
                    'reference_clause': '招标文件资质要求部分',
                    'system_status': 'passed',
                    'risk_level': 'info',
                })

        return checklist

    def _check_price_compliance(self) -> list[dict]:
        """
        Check if final price is within budget limit.

        Rules:
        - boss_final_price > budget_limit → risk='fatal',   status='failed'
        - boss_final_price <= budget_limit → risk='info',   status='passed'
        - no pricing decision → returns []
        """
        pricing = self._load_pricing_decision()

        if not pricing:
            return []

        boss_price = pricing.boss_final_price
        budget_limit = pricing.budget_limit

        if budget_limit is None:
            return []

        if boss_price > budget_limit:
            return [{
                'source_type': 'system_parsed',
                'check_category': 'price_compliance',
                'check_title': '报价超限价检查',
                'check_description': (
                    f"定价 {boss_price} 万 > 预算限价 {budget_limit} 万，"
                    "可能导致直接废标"
                ),
                'reference_clause': '招标文件投标须知',
                'system_status': 'failed',
                'risk_level': 'fatal',
            }]

        return [{
            'source_type': 'system_parsed',
            'check_category': 'price_compliance',
            'check_title': '报价合规检查',
            'check_description': f"定价 {boss_price} 万 ≤ 预算限价 {budget_limit} 万",
            'reference_clause': '招标文件投标须知',
            'system_status': 'passed',
            'risk_level': 'info',
        }]

    def _check_document_integrity(self) -> list[dict]:
        """
        Check that the confirmed tech proposal covers all required sections.

        Loads required_sections from tender.extracted_scoring_std (JSON list) and
        compares against tech_proposal.generated_content['sections'].
        Missing required sections → risk='fatal', status='failed'.
        """
        tech_proposal = self._load_tech_proposal()
        tender = self._load_tender()

        checklist: list[dict] = []

        if not tech_proposal:
            # No confirmed tech proposal found
            checklist.append({
                'source_type': 'content_integrity',
                'check_category': 'document_integrity',
                'check_title': '技术标完整性检查',
                'check_description': '未找到已确认的技术标方案',
                'reference_clause': '技术标生成结果',
                'system_status': 'warning',
                'risk_level': 'warning',
            })
            return checklist

        # Load required sections from tender
        required_sections: list = []
        if tender and tender.extracted_scoring_std:
            import json
            try:
                required_sections = json.loads(tender.extracted_scoring_std)
            except (json.JSONDecodeError, TypeError):
                required_sections = []

        # Load generated sections from tech proposal
        generated_content = tech_proposal.generated_content or {}
        generated_sections: list = generated_content.get('sections', [])

        if not required_sections and not generated_sections:
            # No required_sections defined and tech proposal is empty
            checklist.append({
                'source_type': 'content_integrity',
                'check_category': 'document_integrity',
                'check_title': '技术标完整性检查',
                'check_description': '技术标内容为空，请确认是否已生成技术方案',
                'reference_clause': '技术标生成结果',
                'system_status': 'warning',
                'risk_level': 'warning',
            })
            return checklist

        # Check each required section has a corresponding generated section
        generated_titles = {s.get('section_title') or s.get('title') for s in generated_sections}
        generated_titles = {t for t in generated_titles if t}  # filter None/empty

        for req in required_sections:
            req_name = req.get('name') or req.get('section_title') or req.get('title', '')
            if not req_name:
                continue

            matched = any(req_name in gen_title or gen_title in req_name for gen_title in generated_titles)
            if not matched:
                weight = req.get('weight', req.get('score_weight', '?'))
                checklist.append({
                    'source_type': 'content_integrity',
                    'check_category': 'document_integrity',
                    'check_title': f"技术标章节缺失：{req_name}",
                    'check_description': (
                        f"评分项 '{req_name}' （{weight} 分）在技术标中无对应章节"
                    ),
                    'reference_clause': f"评分标准：{req_name}",
                    'system_status': 'failed',
                    'risk_level': 'fatal',
                })

        return checklist

    def _check_signature_seal(self) -> list[dict]:
        """
        STUB: Signature and seal check.

        Returns:
            Empty list — full implementation requires PDF parsing + OCR.
        """
        return []

    def _check_seal_requirements(self) -> list[dict]:
        """
        STUB: Seal requirements check.

        Reads tender.extracted_seal_requirements if present and generates
        warning items for now.
        """
        tender = self._load_tender()
        if not tender:
            return []

        seal_reqs = getattr(tender, 'extracted_seal_requirements', None)
        if not seal_reqs:
            return []

        return []


# ─── Standalone Helper ───────────────────────────────────────────────────────


def archive_project_to_abandoned_drafts(
    db: Session,
    project_id: int,
    termination_stage: str,
    termination_reason: str,
    user_id: int,
) -> None:
    """
    Archive a project to the abandoned drafts table.

    Called when a boss override terminates a project during formal review,
    pricing, or tech generation stage.

    Args:
        db: SQLAlchemy Session
        project_id: project being terminated
        termination_stage: 'formal_review' | 'pricing' | 'tech_generation'
        termination_reason: human-readable reason for termination
        user_id: ID of the user who triggered the termination
    """
    from app.models.formal_review import AbandonedDraft  # noqa: F401
    from app.models.pricing import PricingDecision  # noqa: F401

    # Find latest decided pricing decision (if any)
    pricing_decision_id = None
    pricing = (
        db.query(PricingDecision)
        .filter(
            PricingDecision.project_id == project_id,
            PricingDecision.status == 'decided',
        )
        .order_by(PricingDecision.id.desc())
        .first()
    )
    if pricing:
        pricing_decision_id = pricing.id

    draft = AbandonedDraft(
        project_id=project_id,
        termination_stage=termination_stage,
        termination_reason=termination_reason,
        termination_by=user_id,
        can_be_revived=True,
        pricing_decision_id=pricing_decision_id,
    )
    db.add(draft)
    db.commit()
