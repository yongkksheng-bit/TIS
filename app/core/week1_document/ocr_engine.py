"""PaddleOCR Engine Wrapper.

Provides structured OCR extraction with per-field confidence scores.
Integrates Task 4 normalizers for date/text cleaning.
"""
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False
    logger.warning("PaddleOCR not available, OCR will return mock data")

from app.utils.text_utils import normalize_ocr_text
from app.utils.datetime_utils import parse_ocr_date


@dataclass
class FieldConfidence:
    """A single extracted field with its confidence score.

    Attributes:
        field: Field name (e.g., 'credit_code', 'company_name').
        value: Extracted value text.
        confidence: Confidence score between 0 and 1.
        bbox: Optional bounding box with x, y, width, height.
    """
    field: str
    value: str
    confidence: float
    bbox: Optional[dict] = None

    def is_low_confidence(self) -> bool:
        """Check if confidence is below 0.8 threshold for manual review."""
        return self.confidence < 0.8


@dataclass
class OCRResult:
    """Result of OCR processing on a single image.

    Attributes:
        raw_text: Full OCR text output from the image.
        fields: List of extracted fields with confidence scores.
        image_type: Type of image (e.g., 'business_license', 'certification').
    """
    raw_text: str
    fields: list[FieldConfidence]
    image_type: str

    def get_warnings(self) -> list[FieldConfidence]:
        """Return fields with low confidence that need manual review."""
        return [f for f in self.fields if f.is_low_confidence()]


class OCREngine:
    """PaddleOCR wrapper with per-field confidence and normalizer integration.

    Provides:
    - Per-field confidence scores from PaddleOCR
    - Integration with Task 4 text_utils.normalize_ocr_text
    - Integration with Task 4 datetime_utils.parse_ocr_date
    - Graceful error handling (returns empty result on failure)
    """

    def __init__(self, use_gpu: bool = False, lang: str = 'ch'):
        """Initialize OCR engine.

        Args:
            use_gpu: Whether to use GPU acceleration.
            lang: Language code ('ch' for Chinese, 'en' for English).
        """
        if not PADDLEOCR_AVAILABLE:
            self._mock = True
            self._engine = None
            logger.info("OCREngine initialized in MOCK mode (PaddleOCR unavailable)")
        else:
            self._mock = False
            self._engine = PaddleOCR(
                use_angle_cls=True,
                lang=lang,
                use_gpu=use_gpu,
                show_log=False,
            )
            logger.info("OCREngine initialized with PaddleOCR")

    def recognize(self, image_path: str, image_type: str = 'other') -> OCRResult:
        """Perform OCR on image, integrate normalizers, handle errors gracefully.

        Args:
            image_path: Path to the image file.
            image_type: Type classification of the image for field extraction.

        Returns:
            OCRResult with raw text, extracted fields, and image type.
        """
        if self._mock:
            return self._mock_result(image_type)

        try:
            result = self._engine.ocr(image_path, cls=True)
            if not result or not result[0]:
                return OCRResult(raw_text='', fields=[], image_type=image_type)

            full_lines = []
            field_boxes = []
            for line in result[0]:
                box, (text, confidence) = line
                full_lines.append(text)
                bbox = {
                    'x': box[0][0],
                    'y': box[0][1],
                    'width': box[2][0] - box[0][0],
                    'height': box[2][1] - box[0][1]
                }
                field_boxes.append((text, confidence, bbox))

            raw_text = '\n'.join(full_lines)
            # Normalize the raw text using Task 4 text_utils
            normalized_text = normalize_ocr_text(raw_text)
            fields = self._extract_fields(normalized_text, field_boxes, image_type)

            return OCRResult(
                raw_text=raw_text,
                fields=fields,
                image_type=image_type
            )

        except Exception as e:
            logger.warning(f"OCR failed for {image_path}: {e}, returning empty result")
            # Preserve original error state but don't block pipeline
            return OCRResult(raw_text='', fields=[], image_type=image_type)

    def _mock_result(self, image_type: str) -> OCRResult:
        """Return empty mock result when PaddleOCR unavailable."""
        return OCRResult(raw_text='', fields=[], image_type=image_type)

    def _extract_fields(
        self,
        raw_text: str,
        field_boxes: list,
        image_type: str
    ) -> list[FieldConfidence]:
        """Extract type-specific fields from OCR text.

        Args:
            raw_text: Normalized OCR text.
            field_boxes: List of (text, confidence, bbox) tuples.
            image_type: Image type for field extraction strategy.

        Returns:
            List of extracted FieldConfidence objects.
        """
        if image_type == 'business_license':
            return self._extract_business_license(raw_text, field_boxes)
        elif image_type == 'certification':
            return self._extract_certification(raw_text, field_boxes)
        return []

    def _extract_business_license(
        self,
        text: str,
        boxes: list
    ) -> list[FieldConfidence]:
        """Extract fields from business license images."""
        import re
        fields = []

        # Credit code pattern - 18 character alphanumeric
        credit_match = re.search(r'([0-9A-Z]{18})', text)
        if credit_match:
            bbox = self._find_box_for_text(boxes, credit_match.group(1))
            fields.append(FieldConfidence(
                field='credit_code',
                value=credit_match.group(1),
                confidence=0.95,
                bbox=bbox,
            ))

        # Company name pattern
        company_match = re.search(r'([^\n]+?有限公司)', text)
        if company_match:
            bbox = self._find_box_for_text(boxes, company_match.group(1))
            fields.append(FieldConfidence(
                field='company_name',
                value=company_match.group(1),
                confidence=0.85,
                bbox=bbox,
            ))

        # Registration capital
        capital_match = re.search(r'注册[资金本]?\s*([0-9,.]+)\s*(万[元芽]?|元)?', text)
        if capital_match:
            bbox = self._find_box_for_text(boxes, capital_match.group(0))
            fields.append(FieldConfidence(
                field='registered_capital',
                value=capital_match.group(1),
                confidence=0.80,
                bbox=bbox,
            ))

        # Address
        addr_match = re.search(r'(地址|住所)\s*[:：]?\s*([^\n]+)', text)
        if addr_match:
            bbox = self._find_box_for_text(boxes, addr_match.group(0))
            fields.append(FieldConfidence(
                field='address',
                value=addr_match.group(2).strip(),
                confidence=0.75,
                bbox=bbox,
            ))

        return fields

    def _extract_certification(
        self,
        text: str,
        boxes: list
    ) -> list[FieldConfidence]:
        """Extract fields from certification images."""
        import re
        fields = []

        # Cert name - look for common cert patterns
        cert_match = re.search(r'(食品经营许可证|营业执照|ISO\d+.*认证|证书)', text)
        if cert_match:
            bbox = self._find_box_for_text(boxes, cert_match.group(1))
            fields.append(FieldConfidence(
                field='cert_name',
                value=cert_match.group(1),
                confidence=0.80,
                bbox=bbox,
            ))

        # Certificate number
        cert_num_match = re.search(r'(证书编号|证号|编号)\s*[:：]?\s*([A-Z0-9]{10,})', text)
        if cert_num_match:
            bbox = self._find_box_for_text(boxes, cert_num_match.group(0))
            fields.append(FieldConfidence(
                field='cert_number',
                value=cert_num_match.group(2),
                confidence=0.85,
                bbox=bbox,
            ))

        return fields

    def _find_box_for_text(
        self,
        boxes: list,
        text: str
    ) -> Optional[dict]:
        """Find bounding box for a specific text in the boxes list.

        Args:
            boxes: List of (text, confidence, bbox) tuples.
            text: Text to search for.

        Returns:
            Bounding box dict or None if not found.
        """
        for item_text, confidence, bbox in boxes:
            if text in item_text:
                return bbox
        return None
