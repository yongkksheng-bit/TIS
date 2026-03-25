"""Tests for DocumentOCRPipeline."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from app.core.week1_document.parser import DocumentOCRPipeline
from app.models.document import DocumentImage, OcrExtraction
from app.models.project import Project
from app.models.enums import ProjectStatus


class TestDocumentOCRPipeline:
    """Tests for DocumentOCRPipeline class."""

    def test_pipeline_stores_extraction_to_db(self, session, seed_certs):
        """Pipeline should store OCR results to ocr_extractions table."""
        pipeline = DocumentOCRPipeline(session)

        mock_images = [MagicMock(
            page_number=1,
            image_bytes=b'fake_image_data',
            image_ext='png',
            md5_hash='abc123',
            width=100,
            height=100
        )]

        with patch.object(pipeline.image_extractor, 'extract_images', return_value=mock_images):
            with patch.object(pipeline.ocr_engine, 'recognize') as mock_ocr:
                mock_ocr.return_value = MagicMock(
                    raw_text='营业执照\n统一社会信用代码 91110000XXXXXXXXXX',
                    fields=[
                        MagicMock(field='cert_name', value='营业执照', confidence=0.95,
                                  bbox={'x': 0, 'y': 0, 'width': 100, 'height': 20}),
                        MagicMock(field='credit_code', value='91110000XXXXXXXXXX', confidence=0.95,
                                  bbox={'x': 0, 'y': 20, 'width': 200, 'height': 20}),
                    ],
                    image_type='business_license'
                )
                result = pipeline.process_pdf('/fake/path.pdf', project_id=1)

        assert result['status'] == 'success'
        assert result['processed_images'] == 1

        # Verify OCR extraction was stored
        extractions = session.query(OcrExtraction).all()
        assert len(extractions) == 2
        field_names = {e.field_name for e in extractions}
        assert 'cert_name' in field_names
        assert 'credit_code' in field_names

    def test_pipeline_sets_is_validated_false(self, session, seed_certs):
        """All stored extractions should have is_validated=False."""
        pipeline = DocumentOCRPipeline(session)

        mock_images = [MagicMock(
            page_number=1,
            image_bytes=b'fake_image_data',
            image_ext='png',
            md5_hash='abc123',
            width=100,
            height=100
        )]

        with patch.object(pipeline.image_extractor, 'extract_images', return_value=mock_images):
            with patch.object(pipeline.ocr_engine, 'recognize') as mock_ocr:
                mock_ocr.return_value = MagicMock(
                    raw_text='营业执照\n统一社会信用代码 91110000XXXXXXXXXX',
                    fields=[
                        MagicMock(field='cert_name', value='营业执照', confidence=0.95,
                                  bbox={'x': 0, 'y': 0, 'width': 100, 'height': 20}),
                    ],
                    image_type='business_license'
                )
                pipeline.process_pdf('/fake/path.pdf', project_id=1)

        # Check that all ocr_extractions have is_validated=False
        extractions = session.query(OcrExtraction).all()
        for ext in extractions:
            assert ext.is_validated is False

    def test_pipeline_updates_project_status(self, session, seed_certs):
        """Pipeline should update project status during processing."""
        pipeline = DocumentOCRPipeline(session)

        # Create project first
        project = Project(id=1, project_name='Test Project', status=ProjectStatus.UPLOADED)
        session.add(project)
        session.commit()

        mock_images = [MagicMock(
            page_number=1,
            image_bytes=b'fake_image_data',
            image_ext='png',
            md5_hash='abc123',
            width=100,
            height=100
        )]

        with patch.object(pipeline.image_extractor, 'extract_images', return_value=mock_images):
            with patch.object(pipeline.ocr_engine, 'recognize') as mock_ocr:
                mock_ocr.return_value = MagicMock(
                    raw_text='',
                    fields=[],
                    image_type='other'
                )
                pipeline.process_pdf('/fake/path.pdf', project_id=1)

        project = session.query(Project).get(1)
        # In test DB with raw SQL, status is stored as string
        status_value = project.status.value if hasattr(project.status, 'value') else project.status
        assert status_value == 'parsed'

    def test_pipeline_handles_empty_images(self, session, seed_certs):
        """Pipeline should handle case when no images are extracted."""
        pipeline = DocumentOCRPipeline(session)

        with patch.object(pipeline.image_extractor, 'extract_images', return_value=[]):
            result = pipeline.process_pdf('/fake/path.pdf', project_id=1)

        assert result['status'] == 'success'
        assert result['processed_images'] == 0

    def test_pipeline_stores_normalized_value(self, session, seed_certs):
        """Pipeline should store normalized values for date fields."""
        pipeline = DocumentOCRPipeline(session)

        mock_images = [MagicMock(
            page_number=1,
            image_bytes=b'fake_image_data',
            image_ext='png',
            md5_hash='abc123',
            width=100,
            height=100
        )]

        with patch.object(pipeline.image_extractor, 'extract_images', return_value=mock_images):
            with patch.object(pipeline.ocr_engine, 'recognize') as mock_ocr:
                mock_ocr.return_value = MagicMock(
                    raw_text='有效期限 2024年01月01日',
                    fields=[
                        MagicMock(field='valid_until', value='2024年01月01日', confidence=0.95,
                                  bbox={'x': 0, 'y': 0, 'width': 100, 'height': 20}),
                    ],
                    image_type='certification'
                )
                pipeline.process_pdf('/fake/path.pdf', project_id=1)

        extraction = session.query(OcrExtraction).filter_by(field_name='valid_until').first()
        assert extraction is not None
        assert '2024-01-01' in extraction.normalized_value

    def test_pipeline_stores_raw_text(self, session, seed_certs):
        """Pipeline should store raw OCR text."""
        pipeline = DocumentOCRPipeline(session)

        mock_images = [MagicMock(
            page_number=1,
            image_bytes=b'fake_image_data',
            image_ext='png',
            md5_hash='abc123',
            width=100,
            height=100
        )]

        raw_text_content = '营业执照\n统一社会信用代码 91110000XXXXXXXXXX'

        with patch.object(pipeline.image_extractor, 'extract_images', return_value=mock_images):
            with patch.object(pipeline.ocr_engine, 'recognize') as mock_ocr:
                mock_ocr.return_value = MagicMock(
                    raw_text=raw_text_content,
                    fields=[
                        MagicMock(field='cert_name', value='营业执照', confidence=0.95,
                                  bbox={'x': 0, 'y': 0, 'width': 100, 'height': 20}),
                    ],
                    image_type='business_license'
                )
                pipeline.process_pdf('/fake/path.pdf', project_id=1)

        extraction = session.query(OcrExtraction).first()
        assert raw_text_content[:2000] in extraction.raw_text
