"""Tests for ConfirmationService."""
import pytest
from app.core.week1_document.confirmation_service import ConfirmationService
from app.models.document import OcrExtraction, DocumentImage, BidDocument
from app.models.project import Project


class TestConfirmationService:
    """Tests for ConfirmationService class."""

    def test_cannot_modify_validated_record(self, session, seed_certs):
        """Once is_validated=True, record must be immutable."""
        service = ConfirmationService(session)

        # Create a project and document image first
        project = Project(id=1, project_name='Test Project', status='parsed')
        session.add(project)
        session.flush()

        # Create bid document (required by document_images.document_id)
        bid_doc = BidDocument(id=1, project_id=1, doc_type='business')
        session.add(bid_doc)
        session.flush()

        doc_image = DocumentImage(
            id=1,
            document_id=1,
            project_id=1,
            image_path='/fake/path.png',
            page_number=1,
            image_hash='abc123',
            image_type='business_license',
            ocr_status='success',
        )
        session.add(doc_image)
        session.flush()

        # Create an extraction
        extraction = OcrExtraction(
            id=1,
            image_id=1,
            project_id=1,
            field_name='cert_name',
            field_value='营业执照',
            confidence_score=0.95,
            is_validated=False,
        )
        session.add(extraction)
        session.commit()

        # First validate it
        service.confirm_extraction(extraction_id=1, user_id=1)

        # Verify it's validated
        ext = session.query(OcrExtraction).get(1)
        assert ext.is_validated is True
        assert ext.validated_by == 1

        # Now try to modify it - should raise
        with pytest.raises(ValueError, match="already validated"):
            service.apply_correction(
                extraction_id=1,
                corrected_value='wrong',
                corrected_cert_id=None,
                user_id=2
            )

    def test_confirm_extraction_sets_validated(self, session, seed_certs):
        """confirm_extraction should set is_validated=True and validated_by."""
        service = ConfirmationService(session)

        # Setup
        project = Project(id=1, project_name='Test Project', status='parsed')
        session.add(project)
        session.flush()

        bid_doc = BidDocument(id=1, project_id=1, doc_type='business')
        session.add(bid_doc)
        session.flush()

        doc_image = DocumentImage(
            id=1,
            document_id=1,
            project_id=1,
            image_path='/fake/path.png',
            page_number=1,
            image_hash='abc123',
            image_type='business_license',
            ocr_status='success',
        )
        session.add(doc_image)
        session.flush()

        extraction = OcrExtraction(
            id=1,
            image_id=1,
            project_id=1,
            field_name='cert_name',
            field_value='营业执照',
            confidence_score=0.95,
            is_validated=False,
        )
        session.add(extraction)
        session.commit()

        result = service.confirm_extraction(extraction_id=1, user_id=1)

        assert result['success'] is True
        ext = session.query(OcrExtraction).get(1)
        assert ext.is_validated is True
        assert ext.validated_by == 1

    def test_confirm_all_fails_with_unvalidated(self, session, seed_certs):
        """confirm_all should fail if any extraction is unvalidated."""
        service = ConfirmationService(session)

        # Setup with multiple extractions - one validated, one not
        project = Project(id=1, project_name='Test Project', status='parsed')
        session.add(project)
        session.flush()

        bid_doc = BidDocument(id=1, project_id=1, doc_type='business')
        session.add(bid_doc)
        session.flush()

        doc_image = DocumentImage(
            id=1,
            document_id=1,
            project_id=1,
            image_path='/fake/path.png',
            page_number=1,
            image_hash='abc123',
            image_type='business_license',
            ocr_status='success',
        )
        session.add(doc_image)
        session.flush()

        # One validated
        ext1 = OcrExtraction(
            id=1,
            image_id=1,
            project_id=1,
            field_name='cert_name',
            field_value='营业执照',
            confidence_score=0.95,
            is_validated=True,
            validated_by=1,
        )
        session.add(ext1)

        # One not validated
        ext2 = OcrExtraction(
            id=2,
            image_id=1,
            project_id=1,
            field_name='credit_code',
            field_value='91110000XXXXXXXXXX',
            confidence_score=0.95,
            is_validated=False,
        )
        session.add(ext2)
        session.commit()

        result = service.confirm_all(project_id=1, user_id=1)

        assert result['success'] is False
        assert '未确认' in result['error'] or '项未确认' in result['error']
        assert result['unvalidated_count'] == 1

    def test_confirm_all_succeeds_when_all_validated(self, session, seed_certs):
        """confirm_all should succeed when all extractions are validated."""
        service = ConfirmationService(session)

        # Setup with all extractions validated
        project = Project(id=1, project_name='Test Project', status='parsed')
        session.add(project)
        session.flush()

        bid_doc = BidDocument(id=1, project_id=1, doc_type='business')
        session.add(bid_doc)
        session.flush()

        doc_image = DocumentImage(
            id=1,
            document_id=1,
            project_id=1,
            image_path='/fake/path.png',
            page_number=1,
            image_hash='abc123',
            image_type='business_license',
            ocr_status='success',
        )
        session.add(doc_image)
        session.flush()

        ext1 = OcrExtraction(
            id=1,
            image_id=1,
            project_id=1,
            field_name='cert_name',
            field_value='营业执照',
            confidence_score=0.95,
            is_validated=True,
            validated_by=1,
        )
        session.add(ext1)

        ext2 = OcrExtraction(
            id=2,
            image_id=1,
            project_id=1,
            field_name='credit_code',
            field_value='91110000XXXXXXXXXX',
            confidence_score=0.95,
            is_validated=True,
            validated_by=1,
        )
        session.add(ext2)
        session.commit()

        result = service.confirm_all(project_id=1, user_id=1)

        assert result['success'] is True

    def test_apply_correction_updates_value(self, session, seed_certs):
        """apply_correction should update field_value and normalized_value."""
        service = ConfirmationService(session)

        # Setup
        project = Project(id=1, project_name='Test Project', status='parsed')
        session.add(project)
        session.flush()

        bid_doc = BidDocument(id=1, project_id=1, doc_type='business')
        session.add(bid_doc)
        session.flush()

        doc_image = DocumentImage(
            id=1,
            document_id=1,
            project_id=1,
            image_path='/fake/path.png',
            page_number=1,
            image_hash='abc123',
            image_type='business_license',
            ocr_status='success',
        )
        session.add(doc_image)
        session.flush()

        extraction = OcrExtraction(
            id=1,
            image_id=1,
            project_id=1,
            field_name='cert_name',
            field_value='营业执照',
            confidence_score=0.95,
            is_validated=False,
        )
        session.add(extraction)
        session.commit()

        result = service.apply_correction(
            extraction_id=1,
            corrected_value='食品经营许可证',
            corrected_cert_id=None,
            user_id=1,
            notes='Test correction'
        )

        assert result['success'] is True
        ext = session.query(OcrExtraction).get(1)
        assert ext.field_value == '食品经营许可证'
        assert ext.normalized_value == '食品经营许可证'
        assert ext.is_validated is True
        assert ext.validated_by == 1
        assert ext.validation_notes == 'Test correction'

    def test_get_confirmation_data(self, session, seed_certs):
        """get_confirmation_data should return structured data for UI."""
        service = ConfirmationService(session)

        # Setup
        project = Project(id=1, project_name='Test Project', status='parsed')
        session.add(project)
        session.flush()

        bid_doc = BidDocument(id=1, project_id=1, doc_type='business')
        session.add(bid_doc)
        session.flush()

        doc_image = DocumentImage(
            id=1,
            document_id=1,
            project_id=1,
            image_path='/fake/path.png',
            page_number=1,
            image_hash='abc123',
            image_type='business_license',
            ocr_status='success',
        )
        session.add(doc_image)
        session.flush()

        extraction = OcrExtraction(
            id=1,
            image_id=1,
            project_id=1,
            field_name='cert_name',
            field_value='营业执照',
            confidence_score=0.95,
            is_validated=False,
        )
        session.add(extraction)
        session.commit()

        data = service.get_confirmation_data(project_id=1)

        assert 'images' in data
        assert len(data['images']) == 1
        assert data['images'][0]['page_number'] == 1
        assert len(data['images'][0]['fields']) == 1
        assert data['images'][0]['fields'][0]['field_name'] == 'cert_name'
        assert data['images'][0]['fields'][0]['is_validated'] is False

    def test_extraction_not_found_raises_error(self, session, seed_certs):
        """Should raise ValueError when extraction_id not found."""
        service = ConfirmationService(session)

        with pytest.raises(ValueError, match="not found"):
            service.confirm_extraction(extraction_id=999, user_id=1)

    def test_confirm_extraction_already_validated_raises(self, session, seed_certs):
        """confirm_extraction should raise if already validated."""
        service = ConfirmationService(session)

        # Setup
        project = Project(id=1, project_name='Test Project', status='parsed')
        session.add(project)
        session.flush()

        bid_doc = BidDocument(id=1, project_id=1, doc_type='business')
        session.add(bid_doc)
        session.flush()

        doc_image = DocumentImage(
            id=1,
            document_id=1,
            project_id=1,
            image_path='/fake/path.png',
            page_number=1,
            image_hash='abc123',
            image_type='business_license',
            ocr_status='success',
        )
        session.add(doc_image)
        session.flush()

        extraction = OcrExtraction(
            id=1,
            image_id=1,
            project_id=1,
            field_name='cert_name',
            field_value='营业执照',
            confidence_score=0.95,
            is_validated=True,
            validated_by=1,
        )
        session.add(extraction)
        session.commit()

        with pytest.raises(ValueError, match="Already validated"):
            service.confirm_extraction(extraction_id=1, user_id=2)
