"""Side-by-Side Confirmation Service.

Single Source of Truth: Once is_validated=True, record is immutable.
"""
from typing import Optional
from sqlalchemy.orm import Session
from app.models.document import OcrExtraction, DocumentImage
from app.models.project import Project


class ConfirmationService:
    """Service for managing OCR extraction confirmations.

    This service enforces the immutability constraint: once an extraction
    is validated (is_validated=True), it can NEVER be modified again.
    """

    def __init__(self, db: Session):
        """Initialize service with database session.

        Args:
            db: SQLAlchemy database session.
        """
        self.db = db

    def get_confirmation_data(self, project_id: int) -> dict:
        """Get structured confirmation data for a project.

        Args:
            project_id: ID of the project.

        Returns:
            Dict with images list and pending_review_count.
        """
        images = self.db.query(DocumentImage).filter_by(
            project_id=project_id
        ).order_by(DocumentImage.page_number).all()

        result_images = []
        pending_count = 0

        for img in images:
            extractions = self.db.query(OcrExtraction).filter_by(
                image_id=img.id
            ).all()

            img_fields = []
            for ext in extractions:
                needs_review = ext.confidence_score < 0.8 and not ext.is_validated
                if needs_review:
                    pending_count += 1

                img_fields.append({
                    'id': ext.id,
                    'field_name': ext.field_name,
                    'field_value': ext.field_value,
                    'normalized_value': ext.normalized_value,
                    'confidence': float(ext.confidence_score),
                    'is_validated': ext.is_validated,
                    'standard_cert_suggestion': ext.standard_cert_id,
                    'standard_cert_id': ext.standard_cert_id,
                })

            result_images.append({
                'id': img.id,
                'page_number': img.page_number,
                'image_path': img.image_path,
                'image_type': img.image_type,
                'ocr_status': img.ocr_status,
                'fields': img_fields,
            })

        return {
            'images': result_images,
            'pending_review_count': pending_count
        }

    def apply_correction(
        self,
        extraction_id: int,
        corrected_value: str,
        corrected_cert_id: Optional[int],
        user_id: int,
        notes: str = ''
    ) -> dict:
        """Apply human correction to an extraction.

        This marks the extraction as validated and stores the correction.
        IMPORTANT: Cannot be called on already-validated records.

        Args:
            extraction_id: ID of the extraction to correct.
            corrected_value: The corrected field value.
            corrected_cert_id: Optional standard cert ID to associate.
            user_id: ID of the user making the correction.
            notes: Optional notes about the correction.

        Returns:
            Dict with success status.

        Raises:
            ValueError: If extraction not found or already validated.
        """
        extraction = self.db.query(OcrExtraction).get(extraction_id)
        if not extraction:
            raise ValueError(f"Extraction {extraction_id} not found")
        if extraction.is_validated:
            raise ValueError("Cannot modify already validated record")

        extraction.field_value = corrected_value
        extraction.normalized_value = corrected_value
        if corrected_cert_id is not None:
            extraction.standard_cert_id = corrected_cert_id
        extraction.is_validated = True
        extraction.validated_by = user_id
        extraction.validation_notes = notes or '人工修正'
        self.db.commit()

        return {'success': True, 'extraction_id': extraction_id}

    def confirm_extraction(self, extraction_id: int, user_id: int) -> dict:
        """Confirm that an extraction is correct.

        Marks the extraction as validated without changes.
        IMPORTANT: Cannot be called on already-validated records.

        Args:
            extraction_id: ID of the extraction to confirm.
            user_id: ID of the user confirming.

        Returns:
            Dict with success status.

        Raises:
            ValueError: If extraction not found or already validated.
        """
        extraction = self.db.query(OcrExtraction).get(extraction_id)
        if not extraction:
            raise ValueError(f"Extraction {extraction_id} not found")
        if extraction.is_validated:
            raise ValueError("Already validated")

        extraction.is_validated = True
        extraction.validated_by = user_id
        self.db.commit()

        return {'success': True, 'extraction_id': extraction_id}

    def confirm_all(self, project_id: int, user_id: int) -> dict:
        """Confirm all extractions for a project at once.

        Only succeeds if ALL extractions are already validated.
        This is a batch operation for final project confirmation.

        Args:
            project_id: ID of the project.
            user_id: ID of the user confirming all.

        Returns:
            Dict with success status or error with unvalidated count.
        """
        unvalidated = self.db.query(OcrExtraction).filter(
            OcrExtraction.project_id == project_id,
            OcrExtraction.is_validated == False,
        ).count()

        if unvalidated > 0:
            return {
                'success': False,
                'error': f'还有 {unvalidated} 项未确认',
                'unvalidated_count': unvalidated
            }

        project = self.db.query(Project).get(project_id)
        if project:
            project.status = 'evaluating'
        self.db.commit()

        return {'success': True}
