"""TDD tests for Week 6 Pydantic schemas."""
import pytest
from decimal import Decimal
from datetime import date, datetime
from pydantic import ValidationError
from app.schemas.week6 import (
    BidOutcomeRecordRequest,
    BidOutcomeResponse,
    ReviewAnalysisResponse,
    ReviewConfirmRequest,
    RebidAlertResponse,
    DraftRevivalResponse,
    KnowledgeEvolutionReportResponse,
)


class TestBidOutcomeRecordRequest:
    def test_valid_win_request(self):
        """Valid win request passes validation."""
        req = BidOutcomeRecordRequest(
            outcome_status='win',
            outcome_date=date(2026, 1, 15),
            final_bid_price=150000.00,
            winning_price=145000.00,
            winning_unit='万元',
            our_price_rank=1,
        )
        assert req.outcome_status == 'win'
        assert req.final_bid_price == 150000.00

    def test_valid_disqualified_request(self):
        """Valid disqualified request with disqualification_type passes."""
        req = BidOutcomeRecordRequest(
            outcome_status='disqualified',
            outcome_date=date(2026, 1, 15),
            final_bid_price=150000.00,
            disqualification_reason='Missing signature page',
            disqualification_type='fatal_formal',
        )
        assert req.disqualification_type == 'fatal_formal'

    def test_optional_fields_optional(self):
        """Optional fields can be omitted."""
        req = BidOutcomeRecordRequest(
            outcome_status='lose',
            outcome_date=date(2026, 1, 15),
            final_bid_price=150000.00,
        )
        assert req.winning_price is None
        assert req.disqualification_reason is None

    def test_extract_dna_defaults_true(self):
        """extract_dna defaults to True."""
        req = BidOutcomeRecordRequest(
            outcome_status='win',
            outcome_date=date(2026, 1, 15),
            final_bid_price=150000.00,
        )
        assert req.extract_dna is True

    def test_update_traps_defaults_true(self):
        """update_traps defaults to True."""
        req = BidOutcomeRecordRequest(
            outcome_status='win',
            outcome_date=date(2026, 1, 15),
            final_bid_price=150000.00,
        )
        assert req.update_traps is True

    def test_invalid_outcome_status_rejected(self):
        """Invalid outcome_status is rejected."""
        with pytest.raises(ValidationError):
            BidOutcomeRecordRequest(
                outcome_status='invalid_status',
                outcome_date=date(2026, 1, 15),
                final_bid_price=150000.00,
            )

    def test_invalid_disqualification_type_rejected(self):
        """Invalid disqualification_type is rejected."""
        with pytest.raises(ValidationError):
            BidOutcomeRecordRequest(
                outcome_status='disqualified',
                outcome_date=date(2026, 1, 15),
                final_bid_price=150000.00,
                disqualification_type='invalid_type',
            )


class TestBidOutcomeResponse:
    def test_valid_response(self):
        """Valid response passes validation."""
        resp = BidOutcomeResponse(
            id=1,
            project_id=1,
            outcome_status='win',
            outcome_date=date(2026, 1, 15),
            final_bid_price=150000.00,
            winning_price=145000.00,
            our_price_rank=1,
            is_manual_error=False,
            created_at=datetime(2026, 1, 15, 10, 30, 0),
        )
        assert resp.outcome_status == 'win'
        assert resp.our_price_rank == 1

    def test_optional_fields_nullable(self):
        """Optional fields can be None."""
        resp = BidOutcomeResponse(
            id=1,
            project_id=1,
            outcome_status='lose',
            outcome_date=date(2026, 1, 15),
            final_bid_price=150000.00,
            is_manual_error=False,
            created_at=datetime(2026, 1, 15, 10, 30, 0),
        )
        assert resp.winning_price is None
        assert resp.review_analysis is None

    def test_review_analysis_as_dict(self):
        """review_analysis can be a dict."""
        resp = BidOutcomeResponse(
            id=1,
            project_id=1,
            outcome_status='win',
            outcome_date=date(2026, 1, 15),
            final_bid_price=150000.00,
            review_analysis={"win_factors": ["price"]},
            is_manual_error=False,
            created_at=datetime(2026, 1, 15, 10, 30, 0),
        )
        assert resp.review_analysis["win_factors"][0] == "price"

    def test_round_trip_via_model_validate(self):
        """Response can round-trip via model_validate."""
        resp1 = BidOutcomeResponse(
            id=1,
            project_id=1,
            outcome_status='win',
            outcome_date=date(2026, 1, 15),
            final_bid_price=150000.00,
            is_manual_error=False,
            created_at=datetime(2026, 1, 15, 10, 30, 0),
        )
        resp2 = BidOutcomeResponse.model_validate(resp1.model_dump())
        assert resp2.id == resp1.id
        assert resp2.outcome_status == resp1.outcome_status


class TestReviewAnalysisResponse:
    def test_valid_win_analysis(self):
        """Valid win analysis passes validation."""
        resp = ReviewAnalysisResponse(
            project_id=1,
            outcome_status='win',
            analysis_type='win',
            is_manual_error=False,
            dna_extracted=[1, 2, 3],
            price_strategy={"lowest": True, "margin": 0.05},
            suggestions=["Continue this strategy"],
        )
        assert resp.analysis_type == 'win'
        assert len(resp.dna_extracted) == 3

    def test_disqualification_with_trap(self):
        """Disqualification analysis with detected trap."""
        resp = ReviewAnalysisResponse(
            project_id=1,
            outcome_status='disqualified',
            analysis_type='disqualification',
            detected_trap='NO_SIGNATURE_PAGE',
            is_manual_error=False,
            suggestions=["Add signature page checklist"],
        )
        assert resp.detected_trap == 'NO_SIGNATURE_PAGE'

    def test_manual_error_flag(self):
        """is_manual_error flag is respected."""
        resp = ReviewAnalysisResponse(
            project_id=1,
            outcome_status='lose',
            analysis_type='lose',
            is_manual_error=True,
            suggestions=["Manual data entry error in bid amount"],
        )
        assert resp.is_manual_error is True

    def test_empty_suggestions_allowed(self):
        """Empty suggestions list is allowed."""
        resp = ReviewAnalysisResponse(
            project_id=1,
            outcome_status='win',
            analysis_type='win',
            is_manual_error=False,
            suggestions=[],
        )
        assert len(resp.suggestions) == 0


class TestReviewConfirmRequest:
    def test_valid_confirm_request(self):
        """Valid confirm request passes validation."""
        req = ReviewConfirmRequest(
            confirmed_analysis={"status": "confirmed", "notes": "Reviewed"},
            manual_notes="All checks passed",
            extract_dna=True,
            update_traps=True,
        )
        assert req.extract_dna is True

    def test_extract_dna_defaults_true(self):
        """extract_dna defaults to True."""
        req = ReviewConfirmRequest(
            confirmed_analysis={"status": "confirmed"},
            manual_notes="Reviewed",
        )
        assert req.extract_dna is True

    def test_update_traps_defaults_true(self):
        """update_traps defaults to True."""
        req = ReviewConfirmRequest(
            confirmed_analysis={"status": "confirmed"},
            manual_notes="Reviewed",
        )
        assert req.update_traps is True

    def test_manual_notes_required(self):
        """manual_notes is required."""
        with pytest.raises(ValidationError):
            ReviewConfirmRequest(
                confirmed_analysis={"status": "confirmed"},
            )


class TestRebidAlertResponse:
    def test_rebid_detected(self):
        """Rebid detected with historical project info."""
        resp = RebidAlertResponse(
            is_rebid=True,
            historical_project_id=5,
            historical_outcome='win',
            similarity_score=0.85,
            alert_level='high',
            warnings=["Same project re-bid detected"],
            revivable_drafts=[{"id": 1, "project_name": "Old Project"}],
        )
        assert resp.is_rebid is True
        assert resp.alert_level == 'high'

    def test_no_rebid(self):
        """No rebid when is_rebid is False."""
        resp = RebidAlertResponse(
            is_rebid=False,
            warnings=[],
        )
        assert resp.is_rebid is False
        assert resp.historical_project_id is None

    def test_medium_alert_level(self):
        """Medium alert level is valid."""
        resp = RebidAlertResponse(
            is_rebid=True,
            similarity_score=0.6,
            alert_level='medium',
            warnings=["Similar project found"],
        )
        assert resp.alert_level == 'medium'

    def test_empty_warnings_allowed(self):
        """Empty warnings list is allowed."""
        resp = RebidAlertResponse(
            is_rebid=False,
            warnings=[],
        )
        assert len(resp.warnings) == 0


class TestDraftRevivalResponse:
    def test_valid_response(self):
        """Valid response passes validation."""
        resp = DraftRevivalResponse(
            id=1,
            abandoned_draft_id=5,
            new_project_id=10,
            revival_type='rebid_same_project',
            revived_content={"sections": ["intro"]},
            adaptation_notes="Updated for new project",
            revived_by=1,
            revived_at=datetime(2026, 1, 20, 14, 0, 0),
            is_successful=True,
        )
        assert resp.revival_type == 'rebid_same_project'
        assert resp.is_successful is True

    def test_is_successful_nullable(self):
        """is_successful can be None (not yet determined)."""
        resp = DraftRevivalResponse(
            id=1,
            abandoned_draft_id=5,
            new_project_id=10,
            revival_type='similar_project_reference',
            revived_at=datetime(2026, 1, 20, 14, 0, 0),
            is_successful=None,
        )
        assert resp.is_successful is None

    def test_round_trip_via_model_validate(self):
        """Response can round-trip via model_validate."""
        resp1 = DraftRevivalResponse(
            id=1,
            abandoned_draft_id=5,
            new_project_id=10,
            revival_type='rebid_same_project',
            revived_at=datetime(2026, 1, 20, 14, 0, 0),
        )
        resp2 = DraftRevivalResponse.model_validate(resp1.model_dump())
        assert resp2.id == resp1.id
        assert resp2.revival_type == resp1.revival_type


class TestKnowledgeEvolutionReportResponse:
    def test_valid_report(self):
        """Valid report passes validation."""
        resp = KnowledgeEvolutionReportResponse(
            total_chunks=100,
            deprecated_this_month=5,
            weighted_by_wins=20,
            new_traps_added=3,
            avg_quality_score_trend='up',
        )
        assert resp.avg_quality_score_trend == 'up'

    def test_stable_trend(self):
        """stable trend is valid."""
        resp = KnowledgeEvolutionReportResponse(
            total_chunks=100,
            deprecated_this_month=0,
            weighted_by_wins=10,
            new_traps_added=0,
            avg_quality_score_trend='stable',
        )
        assert resp.avg_quality_score_trend == 'stable'

    def test_down_trend(self):
        """down trend is valid."""
        resp = KnowledgeEvolutionReportResponse(
            total_chunks=100,
            deprecated_this_month=10,
            weighted_by_wins=5,
            new_traps_added=2,
            avg_quality_score_trend='down',
        )
        assert resp.avg_quality_score_trend == 'down'
