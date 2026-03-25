"""Document OCR Pipeline - Main Orchestrator."""
from pathlib import Path
from typing import Optional
import logging
from sqlalchemy.orm import Session

from app.core.week1_document.image_extractor import ImageExtractor
from app.core.week1_document.ocr_engine import OCREngine, FieldConfidence
from app.utils.datetime_utils import parse_ocr_date
from app.utils.text_utils import normalize_ocr_text
from app.core.week1_document.cert_matcher import StandardCertMatcher
from app.models.document import DocumentImage, OcrExtraction, BidDocument
from app.models.project import Project

logger = logging.getLogger(__name__)


class DocumentOCRPipeline:
    """Document OCR Pipeline orchestrating image extraction, OCR, and storage.

    This pipeline:
    1. Extracts images from PDF using ImageExtractor (MD5 deduplication)
    2. Recognizes text using OCREngine
    3. Normalizes OCR text and dates using Task 4 utils
    4. Suggests standard cert matches using StandardCertMatcher
    5. Stores results to ocr_extractions table with is_validated=False
    """

    def __init__(self, db: Session):
        """Initialize pipeline with database session.

        Args:
            db: SQLAlchemy database session.
        """
        self.db = db
        self.image_extractor = ImageExtractor()
        self.ocr_engine = OCREngine()
        self.cert_matcher = StandardCertMatcher(db)

    def process_pdf(self, pdf_path: str, project_id: int) -> dict:
        """Process a PDF document through the OCR pipeline.

        Args:
            pdf_path: Path to the PDF file.
            project_id: ID of the project this document belongs to.

        Returns:
            Dict with processing results {'processed_images': int, 'status': str}
        """
        project = self.db.query(Project).get(project_id)
        if project:
            project.status = 'parsing'
            self.db.commit()

        # Get or create a BidDocument for this project
        bid_doc = self.db.query(BidDocument).filter_by(project_id=project_id).first()
        if not bid_doc:
            bid_doc = BidDocument(project_id=project_id, doc_type='business')
            self.db.add(bid_doc)
            self.db.flush()

        images = self.image_extractor.extract_images(pdf_path)
        processed_count = 0

        for img_data in images:
            try:
                self._process_single_image(
                    image_bytes=img_data.image_bytes,
                    page_number=img_data.page_number,
                    md5_hash=img_data.md5_hash,
                    project_id=project_id,
                    image_ext=img_data.image_ext,
                    document_id=bid_doc.id,
                )
                processed_count += 1
            except Exception as e:
                logger.error(f"Failed to process image: {e}")

        if project:
            project.status = 'parsed'
            self.db.commit()

        return {'processed_images': processed_count, 'status': 'success'}

    def _process_single_image(
        self,
        image_bytes: bytes,
        page_number: int,
        md5_hash: str,
        project_id: int,
        image_ext: str,
        document_id: int,
    ) -> None:
        """Process a single image through OCR and store results.

        Args:
            image_bytes: Raw image bytes.
            page_number: Page number in the original PDF.
            md5_hash: MD5 hash of the image for deduplication.
            project_id: ID of the project.
            image_ext: Image file extension.
            document_id: ID of the parent BidDocument.
        """
        image_path = self._save_image(image_bytes, project_id, page_number, image_ext)
        image_type = self.image_extractor.classify_image_type(image_bytes)

        doc_image = DocumentImage(
            document_id=document_id,
            project_id=project_id,
            image_path=image_path,
            page_number=page_number,
            image_hash=md5_hash,
            image_type=image_type,
            ocr_status='processing',
        )
        self.db.add(doc_image)
        self.db.flush()

        ocr_result = self.ocr_engine.recognize(image_path, image_type)

        for field_conf in ocr_result.fields:
            self._store_extraction(
                image_id=doc_image.id,
                project_id=project_id,
                field=field_conf,
                raw_text=ocr_result.raw_text,
            )

        doc_image.ocr_status = 'success'
        self.db.commit()

    def _store_extraction(
        self,
        image_id: int,
        project_id: int,
        field: FieldConfidence,
        raw_text: str,
    ) -> None:
        """Store an OCR extraction result to the database.

        Args:
            image_id: ID of the DocumentImage.
            project_id: ID of the project.
            field: FieldConfidence object with field details.
            raw_text: Raw OCR text from the image.
        """
        normalized = self._normalize_field(field)
        cert_suggestion = None
        if field.field == 'cert_name':
            cert_suggestion = self.cert_matcher.suggest_match(field.value)

        extraction = OcrExtraction(
            image_id=image_id,
            project_id=project_id,
            field_name=field.field,
            field_value=field.value,
            confidence_score=field.confidence,
            normalized_value=normalized,
            standard_cert_id=cert_suggestion['cert_id'] if cert_suggestion else None,
            raw_text=raw_text[:2000] if raw_text else None,
            bbox_coords=field.bbox,
            is_validated=False,
        )
        self.db.add(extraction)

    def _normalize_field(self, field: FieldConfidence) -> str:
        """Normalize field value using text utils and date parser.

        Args:
            field: FieldConfidence object with field details.

        Returns:
            Normalized field value string.
        """
        val = normalize_ocr_text(field.value)
        if 'date' in field.field.lower() or 'valid' in field.field.lower():
            parsed = parse_ocr_date(field.value)
            if parsed:
                val = str(parsed)
        return val

    def _save_image(
        self,
        image_bytes: bytes,
        project_id: int,
        page_number: int,
        image_ext: str,
    ) -> str:
        """Save image bytes to a temporary file.

        Args:
            image_bytes: Raw image bytes.
            project_id: ID of the project.
            page_number: Page number in the original PDF.
            image_ext: Image file extension.

        Returns:
            Path to the saved image file.
        """
        import tempfile
        filename = f"{project_id}_p{page_number}.{image_ext}"
        tmp_dir = Path(tempfile.gettempdir()) / "tis_images"
        tmp_dir.mkdir(exist_ok=True)
        filepath = tmp_dir / filename
        filepath.write_bytes(image_bytes)
        return str(filepath)
