"""TDD tests for Week 5 Pydantic schemas."""
import pytest
from decimal import Decimal
from pydantic import ValidationError
from app.schemas.week5 import (
    FormalReviewItemResponse, FormalReviewStatusResponse,
    ReviewItemConfirmRequest, ReviewItemCorrectRequest,
    ManualReviewItemRequest, FinalDocGenerateRequest,
    FinalDocGenerateResponse, AbandonedDraftResponse,
)


class TestFormalReviewItemResponse:
    def test_valid_item_response(self):
        item = FormalReviewItemResponse(
            id=1, project_id=1, source_type='ocr_comparison',
            check_category='qualification_validity', check_title='ISO证书有效期',
            check_description='证书已过期', reference_clause='第三章3.1',
            system_status='failed', risk_level='fatal',
            specialist_status='pending', pdf_highlight_coords={"page": 3},
        )
        assert item.risk_level == 'fatal'
        assert item.specialist_status == 'pending'

    def test_invalid_source_type_rejected(self):
        with pytest.raises(ValidationError):
            FormalReviewItemResponse(source_type='invalid_source')


class TestFormalReviewStatusResponse:
    def test_can_generate_false_when_fatal_pending(self):
        status = FormalReviewStatusResponse(
            project_id=1,
            total_items=5, confirmed_items=3,
            fatal_pending=1, warning_pending=1,
            can_generate=False, blocking_reason="存在1项致命风险未处理"
        )
        assert status.can_generate is False

    def test_can_generate_true_when_all_cleared(self):
        status = FormalReviewStatusResponse(
            project_id=1,
            total_items=5, confirmed_items=5,
            fatal_pending=0, warning_pending=0,
            can_generate=True
        )
        assert status.can_generate is True


class TestReviewItemConfirmRequest:
    def test_notes_optional(self):
        req = ReviewItemConfirmRequest()
        assert req.notes is None


class TestReviewItemCorrectRequest:
    def test_corrected_status_required(self):
        with pytest.raises(ValidationError):
            ReviewItemCorrectRequest(notes="no status")

    def test_valid_correction(self):
        req = ReviewItemCorrectRequest(
            corrected_status='passed',
            corrected_evidence='实际在第5页已签字',
            notes='系统OCR漏识别'
        )
        assert req.corrected_status == 'passed'


class TestManualReviewItemRequest:
    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            ManualReviewItemRequest(check_title="仅标题不够")


class TestFinalDocGenerateRequest:
    def test_defaults(self):
        req = FinalDocGenerateRequest()
        assert req.include_packaging_guide is True
        assert req.document_format == 'word'

    def test_valid_request(self):
        req = FinalDocGenerateRequest(
            include_packaging_guide=True,
            document_format='word'
        )
        assert req.include_packaging_guide is True
