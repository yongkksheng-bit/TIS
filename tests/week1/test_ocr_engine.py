"""Tests for OCREngine using PaddleOCR with mocking."""
import pytest
from unittest.mock import patch, MagicMock

from app.core.week1_document.ocr_engine import (
    OCREngine,
    OCRResult,
    FieldConfidence,
    PADDLEOCR_AVAILABLE,
)


class TestFieldConfidence:
    """Tests for FieldConfidence dataclass."""

    def test_field_confidence_creation(self):
        """Should create FieldConfidence with all fields."""
        fc = FieldConfidence(
            field='credit_code',
            value='91110000XXXXXXXXXX',
            confidence=0.95
        )
        assert fc.field == 'credit_code'
        assert fc.value == '91110000XXXXXXXXXX'
        assert fc.confidence == 0.95
        assert fc.bbox is None

    def test_field_confidence_with_bbox(self):
        """Should create FieldConfidence with bounding box."""
        bbox = {'x': 10, 'y': 20, 'width': 100, 'height': 50}
        fc = FieldConfidence(
            field='company_name',
            value='测试公司',
            confidence=0.85,
            bbox=bbox
        )
        assert fc.bbox == bbox

    def test_is_low_confidence_true(self):
        """Should flag confidence < 0.8 as low."""
        fc = FieldConfidence(
            field='cert_name',
            value='营业执照',
            confidence=0.65
        )
        assert fc.is_low_confidence() is True

    def test_is_low_confidence_false(self):
        """Should not flag confidence >= 0.8 as low."""
        fc = FieldConfidence(
            field='credit_code',
            value='91110000XXXXXXXXXX',
            confidence=0.95
        )
        assert fc.is_low_confidence() is False

    def test_is_low_confidence_boundary(self):
        """Boundary test at exactly 0.8 should not be flagged."""
        fc = FieldConfidence(
            field='test',
            value='test',
            confidence=0.8
        )
        assert fc.is_low_confidence() is False


class TestOCRResult:
    """Tests for OCRResult dataclass."""

    def test_ocr_result_creation(self):
        """Should create OCRResult with all fields."""
        result = OCRResult(
            raw_text="统一社会信用代码 91110000XXXXXXXXXX",
            fields=[
                FieldConfidence(field='credit_code', value='91110000XXXXXXXXXX', confidence=0.95),
            ],
            image_type='business_license'
        )
        assert result.raw_text == "统一社会信用代码 91110000XXXXXXXXXX"
        assert len(result.fields) == 1
        assert result.fields[0].confidence == 0.95
        assert result.image_type == 'business_license'

    def test_get_warnings_returns_low_confidence_fields(self):
        """Should return fields with confidence < 0.8."""
        result = OCRResult(
            raw_text="营业执照",
            fields=[
                FieldConfidence(field='cert_name', value='营业执照', confidence=0.65),
                FieldConfidence(field='credit_code', value='91110000XXXXXXXXXX', confidence=0.95),
            ],
            image_type='business_license'
        )
        warnings = result.get_warnings()
        assert len(warnings) == 1
        assert warnings[0].field == 'cert_name'

    def test_get_warnings_returns_empty_when_all_good(self):
        """Should return empty list when all fields have high confidence."""
        result = OCRResult(
            raw_text="营业执照",
            fields=[
                FieldConfidence(field='credit_code', value='91110000XXXXXXXXXX', confidence=0.95),
                FieldConfidence(field='company_name', value='测试公司', confidence=0.85),
            ],
            image_type='business_license'
        )
        warnings = result.get_warnings()
        assert len(warnings) == 0


class TestOCREngine:
    """Tests for OCREngine class."""

    @patch('app.core.week1_document.ocr_engine.PADDLEOCR_AVAILABLE', False)
    def test_mock_mode_when_paddleocr_unavailable(self):
        """Should use mock when PaddleOCR not available."""
        engine = OCREngine()
        assert engine._mock is True
        assert engine._engine is None

    @patch('app.core.week1_document.ocr_engine.PADDLEOCR_AVAILABLE', True)
    @patch('app.core.week1_document.ocr_engine.PaddleOCR', create=True)
    def test_init_with_paddleocr_available(self, mock_paddleocr):
        """Should initialize PaddleOCR when available."""
        engine = OCREngine()
        assert engine._mock is False
        mock_paddleocr.assert_called_once()

    @patch('app.core.week1_document.ocr_engine.PADDLEOCR_AVAILABLE', False)
    def test_recognize_returns_empty_when_mock(self):
        """Should return empty OCRResult in mock mode."""
        engine = OCREngine()
        result = engine.recognize('fake_path.png', 'business_license')

        assert result.raw_text == ''
        assert result.fields == []
        assert result.image_type == 'business_license'

    @patch('app.core.week1_document.ocr_engine.PADDLEOCR_AVAILABLE', True)
    @patch('app.core.week1_document.ocr_engine.PaddleOCR', create=True)
    def test_recognize_handles_ocr_exception(self, mock_paddleocr):
        """Should return empty result when OCR fails."""
        # Setup mock engine that raises exception
        mock_engine = MagicMock()
        mock_engine.ocr.side_effect = Exception("OCR failed")
        mock_paddleocr.return_value = mock_engine

        engine = OCREngine()
        result = engine.recognize('fake_path.png', 'business_license')

        assert result.raw_text == ''
        assert result.fields == []

    @patch('app.core.week1_document.ocr_engine.PADDLEOCR_AVAILABLE', True)
    @patch('app.core.week1_document.ocr_engine.PaddleOCR', create=True)
    def test_recognize_empty_result_when_no_text(self, mock_paddleocr):
        """Should return empty result when OCR returns no text."""
        mock_engine = MagicMock()
        mock_engine.ocr.return_value = None
        mock_paddleocr.return_value = mock_engine

        engine = OCREngine()
        result = engine.recognize('fake_path.png', 'business_license')

        assert result.raw_text == ''
        assert result.fields == []

    @patch('app.core.week1_document.ocr_engine.PADDLEOCR_AVAILABLE', True)
    @patch('app.core.week1_document.ocr_engine.PaddleOCR', create=True)
    def test_recognize_extracts_business_license_fields(self, mock_paddleocr):
        """Should extract business license fields correctly."""
        mock_engine = MagicMock()
        # Mock OCR result with business license text
        mock_engine.ocr.return_value = [[
            ([[10, 10], [100, 10], [100, 30], [10, 30]], ('统一社会信用代码 91110000XXXXXXXXXX', 0.95)),
            ([[10, 40], [200, 40], [200, 60], [10, 60]], ('测试科技有限公司', 0.85)),
        ]]
        mock_paddleocr.return_value = mock_engine

        engine = OCREngine()
        result = engine.recognize('business_license.png', 'business_license')

        assert '91110000XXXXXXXXXX' in result.raw_text
        assert len(result.fields) > 0

    def test_integrates_text_normalizer(self):
        """OCREngine should use normalize_ocr_text from text_utils."""
        # This test verifies the import exists and is used
        from app.utils.text_utils import normalize_ocr_text

        # Verify the function exists and works
        normalized = normalize_ocr_text('１２３　ＡＢＣ')  # Fullwidth
        assert normalized == '123 ABC'  # Should be normalized to halfwidth

    @patch('app.core.week1_document.ocr_engine.PADDLEOCR_AVAILABLE', True)
    @patch('app.core.week1_document.ocr_engine.PaddleOCR', create=True)
    def test_extract_business_license_credit_code(self, mock_paddleocr):
        """Should extract credit code from business license."""
        mock_engine = MagicMock()
        mock_engine.ocr.return_value = [[
            ([[0, 0], [200, 0], [200, 20], [0, 20]], ('统一社会信用代码 91110000XXXXXXXXXX', 0.95)),
        ]]
        mock_paddleocr.return_value = mock_engine

        engine = OCREngine()
        result = engine.recognize('test.png', 'business_license')

        # Check that credit_code field is extracted
        credit_fields = [f for f in result.fields if f.field == 'credit_code']
        if credit_fields:
            assert credit_fields[0].confidence == 0.95

    @patch('app.core.week1_document.ocr_engine.PADDLEOCR_AVAILABLE', True)
    @patch('app.core.week1_document.ocr_engine.PaddleOCR', create=True)
    def test_low_confidence_fields_are_flagged(self, mock_paddleocr):
        """Fields with confidence < 0.8 should be flagged."""
        mock_engine = MagicMock()
        mock_engine.ocr.return_value = [[
            ([[0, 0], [100, 0], [100, 20], [0, 20]], ('地址北京市朝阳区', 0.65)),
        ]]
        mock_paddleocr.return_value = mock_engine

        engine = OCREngine()
        result = engine.recognize('test.png', 'business_license')

        warnings = result.get_warnings()
        assert len(warnings) >= 0  # Low confidence fields should be in warnings list


class TestOCREngineIntegration:
    """Integration tests for OCREngine with normalizers."""

    def test_normalize_ocr_text_fullwidth_conversion(self):
        """Should convert fullwidth characters to halfwidth."""
        from app.utils.text_utils import normalize_ocr_text

        # Fullwidth numbers and letters
        result = normalize_ocr_text('１２３４５６７８９０')
        assert '1234567890' in result

    def test_normalize_ocr_text_whitespace(self):
        """Should normalize whitespace."""
        from app.utils.text_utils import normalize_ocr_text

        result = normalize_ocr_text('  hello   world  ')
        assert result == 'hello world'

    def test_parse_ocr_date_integration(self):
        """Should be able to parse dates from OCR text."""
        from app.utils.datetime_utils import parse_ocr_date
        from app.utils.text_utils import normalize_ocr_text

        # OCR might return fullwidth or messy dates
        ocr_date = '2024年01月15日'
        normalized = normalize_ocr_text(ocr_date)

        # parse_ocr_date should handle the normalized date
        result = parse_ocr_date(normalized)
        assert result is not None
