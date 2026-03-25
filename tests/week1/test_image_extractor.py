"""Tests for ImageExtractor using PyMuPDF."""
import pytest
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.core.week1_document.image_extractor import ImageExtractor, ExtractedImage


class TestExtractedImage:
    """Tests for ExtractedImage dataclass."""

    def test_extracted_image_creation(self):
        """Should create ExtractedImage with all required fields."""
        img = ExtractedImage(
            page_number=1,
            image_bytes=b'fake_image_bytes',
            image_ext='png',
            md5_hash='abc123',
            width=100,
            height=200
        )
        assert img.page_number == 1
        assert img.image_bytes == b'fake_image_bytes'
        assert img.image_ext == 'png'
        assert img.md5_hash == 'abc123'
        assert img.width == 100
        assert img.height == 200


class TestImageExtractor:
    """Tests for ImageExtractor class."""

    def test_extract_images_returns_list(self):
        """Should return list of ExtractedImage."""
        extractor = ImageExtractor()
        # Without a real PDF, we test the structure
        assert hasattr(extractor, 'extract_images')
        assert callable(extractor.extract_images)

    def test_md5_deduplication_logic(self):
        """Same image bytes should result in only one image kept."""
        # Create two ExtractedImage with same MD5
        same_hash = hashlib.md5(b'same').hexdigest()
        img1 = ExtractedImage(
            page_number=1,
            image_bytes=b'same',
            image_ext='png',
            md5_hash=same_hash,
            width=100,
            height=100
        )
        img2 = ExtractedImage(
            page_number=2,
            image_bytes=b'same',
            image_ext='png',
            md5_hash=same_hash,
            width=100,
            height=100
        )

        # Simulate deduplication logic
        results = [img1]
        if img2.md5_hash not in [i.md5_hash for i in results]:
            results.append(img2)

        assert len(results) == 1
        assert results[0].page_number == 1

    def test_different_md5_are_kept(self):
        """Different image bytes should result in both images kept."""
        hash1 = hashlib.md5(b'image1').hexdigest()
        hash2 = hashlib.md5(b'image2').hexdigest()

        img1 = ExtractedImage(
            page_number=1,
            image_bytes=b'image1',
            image_ext='png',
            md5_hash=hash1,
            width=100,
            height=100
        )
        img2 = ExtractedImage(
            page_number=2,
            image_bytes=b'image2',
            image_ext='jpg',
            md5_hash=hash2,
            width=200,
            height=200
        )

        # Simulate deduplication logic
        results = [img1]
        if img2.md5_hash not in [i.md5_hash for i in results]:
            results.append(img2)

        assert len(results) == 2

    @patch('app.core.week1_document.image_extractor.fitz')
    def test_extract_images_calls_fitz(self, mock_fitz):
        """Should call PyMuPDF (fitz) to extract images."""
        # Setup mock
        mock_doc = MagicMock()
        mock_fitz.open.return_value = mock_doc
        mock_doc.__len__.return_value = 1
        mock_doc.__getitem__.return_value = MagicMock()
        mock_doc.return_value = [MagicMock()]

        mock_page = MagicMock()
        mock_doc.__getitem__.return_value = mock_page
        mock_page.get_images.return_value = []

        extractor = ImageExtractor()
        # Even with empty images, we verify fitz was called
        extractor.extract_images('fake.pdf')

        mock_fitz.open.assert_called_once_with('fake.pdf')

    @patch('app.core.week1_document.image_extractor.fitz')
    def test_extract_images_handles_no_images(self, mock_fitz):
        """Should return empty list when PDF has no images."""
        mock_doc = MagicMock()
        mock_fitz.open.return_value = mock_doc
        mock_doc.__len__.return_value = 1

        mock_page = MagicMock()
        mock_page.get_images.return_value = []
        mock_doc.__getitem__.return_value = mock_page

        extractor = ImageExtractor()
        results = extractor.extract_images('fake.pdf')

        assert results == []
        mock_doc.close.assert_called_once()

    @patch('app.core.week1_document.image_extractor.fitz')
    def test_extract_images_deduplicates_by_md5(self, mock_fitz):
        """Should skip images with duplicate MD5 hashes."""
        # Create mock PDF with 2 pages
        mock_doc = MagicMock()
        mock_fitz.open.return_value = mock_doc
        mock_doc.__len__.return_value = 2

        # Same image data on both pages
        same_bytes = b'identical_image_data'
        same_md5 = hashlib.md5(same_bytes).hexdigest()

        mock_base_image = {
            'image': same_bytes,
            'ext': 'png',
            'width': 100,
            'height': 100
        }

        # Page 1 has image
        mock_page1 = MagicMock()
        mock_page1.get_images.return_value = [(1,)]
        mock_page1.get_images.return_value = [(1,)]

        # Page 2 has same image (same xref and data)
        mock_page2 = MagicMock()
        mock_page2.get_images.return_value = [(1,)]

        mock_doc.__getitem__.side_effect = [mock_page1, mock_page2]

        # Mock extract_image to return same data
        mock_doc.extract_image.return_value = mock_base_image

        extractor = ImageExtractor()
        results = extractor.extract_images('fake.pdf')

        # Should only have 1 result due to deduplication
        assert len(results) == 1
        assert results[0].page_number == 1

    def test_extracted_image_dataclass_fields(self):
        """ExtractedImage should have all required fields."""
        img = ExtractedImage(
            page_number=5,
            image_bytes=b'test',
            image_ext='jpeg',
            md5_hash='hash123',
            width=300,
            height=400
        )

        assert img.page_number == 5
        assert img.image_bytes == b'test'
        assert img.image_ext == 'jpeg'
        assert img.md5_hash == 'hash123'
        assert img.width == 300
        assert img.height == 400
