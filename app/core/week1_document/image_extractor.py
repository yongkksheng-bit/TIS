"""Image Extractor: PDF image extraction with MD5 deduplication using PyMuPDF."""
import fitz
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


@dataclass
class ExtractedImage:
    """Represents an image extracted from a PDF page."""
    page_number: int
    image_bytes: bytes
    image_ext: str
    md5_hash: str
    width: int
    height: int


class ImageExtractor:
    """Extract images from PDF using PyMuPDF with MD5 deduplication.

    Ensures that within a single extraction task, duplicate images
    (same MD5 hash) are skipped to avoid redundant OCR processing.
    """

    def extract_images(self, pdf_path: str | Path) -> list[ExtractedImage]:
        """Extract all images from PDF, deduplicated by MD5.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            List of ExtractedImage objects, deduplicated by MD5 hash.
        """
        doc = fitz.open(str(pdf_path))
        seen_hashes: set[str] = set()
        results: list[ExtractedImage] = []

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                for img_index, img in enumerate(page.get_images(full=True)):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image['image']
                    image_ext = base_image['ext']

                    md5_hash = hashlib.md5(image_bytes).hexdigest()
                    if md5_hash in seen_hashes:
                        continue
                    seen_hashes.add(md5_hash)

                    results.append(ExtractedImage(
                        page_number=page_num + 1,
                        image_bytes=image_bytes,
                        image_ext=image_ext,
                        md5_hash=md5_hash,
                        width=base_image['width'],
                        height=base_image['height'],
                    ))
        finally:
            doc.close()

        return results
