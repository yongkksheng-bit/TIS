"""BidPDFHighlighter — overlays colored annotations on bid PDF for review items using PyMuPDF."""
import fitz  # PyMuPDF
import os
from typing import List


class BidPDFHighlighter:
    """
    Applies colored highlight annotations to a PDF based on formal review items.

    Color mapping:
    - fatal  → red    (1, 0, 0)
    - warning → yellow (1, 0.8, 0)
    - info   → green  (0, 1, 0)
    """

    def __init__(self, input_pdf_path: str = None):
        """Initialize with optional input PDF path."""
        self.input_pdf_path = input_pdf_path

    @staticmethod
    def _color_for_risk(risk_level: str) -> tuple:
        """Return RGB tuple for a given risk level."""
        return {
            'fatal': (1, 0, 0),        # red
            'warning': (1, 0.8, 0),   # yellow
            'info': (0, 1, 0),         # green
        }.get(risk_level, (0.5, 0.5, 0.5))  # grey default

    def highlight_keywords(self, input_pdf_path: str, output_pdf_path: str, keywords: list[str]) -> str:
        """
        Open the PDF, search for each keyword, and apply YELLOW highlight annotations.

        Args:
            input_pdf_path: Path to the input PDF.
            output_pdf_path: Path for the annotated output PDF. If None, auto-generates
                             as {input_pdf_path}_annotated.pdf.
            keywords: List of keyword strings to search for and highlight.

        Returns:
            Path to the annotated output PDF.
        """
        if output_pdf_path is None:
            output_pdf_path = f"{input_pdf_path}_annotated.pdf"

        doc = fitz.open(input_pdf_path)
        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                for keyword in keywords:
                    # Search for all occurrences of the keyword on this page
                    matches = page.search_for(keyword)
                    for match in matches:
                        # Apply YELLOW highlight annotation
                        highlight = page.add_highlight_annot(match)
                        highlight.set_colors(stroke=(1, 1, 0))  # yellow
                        highlight.update()
            doc.save(output_pdf_path)
        finally:
            doc.close()

        return output_pdf_path

    def apply_highlights(self, review_items: list[dict], output_path: str) -> str:
        """
        Apply highlight annotations to PDF pages based on review_items.

        Args:
            review_items: list of dicts with keys:
                - check_title: str
                - risk_level: str (fatal/warning/info)
                - pdf_highlight_coords: dict or None
                  coords: {page: int (1-indexed), x: float, y: float, width: float, height: float}
            output_path: output PDF path.

        Returns:
            Path to the annotated PDF.
        """
        if self.input_pdf_path is None:
            raise ValueError("input_pdf_path must be set to use apply_highlights")

        doc = fitz.open(self.input_pdf_path)
        try:
            for item in review_items:
                coords = item.get('pdf_highlight_coords')
                if not coords:
                    continue

                page_num = coords.get('page', 1)
                if page_num < 1 or page_num > len(doc):
                    continue

                page = doc[page_num - 1]  # 0-indexed
                color = self._color_for_risk(item.get('risk_level', 'info'))

                x = float(coords.get('x', 0))
                y = float(coords.get('y', 0))
                w = float(coords.get('width', 100))
                h = float(coords.get('height', 30))

                rect = fitz.Rect(x, y, x + w, y + h)
                highlight = page.add_highlight_annot(rect)
                highlight.set_colors(stroke=color, fill=(*color, 0.2))
                highlight.update()

                # Add text annotation
                title = item.get('check_title', '')[:50]
                risk_label = item.get('risk_level', '?').upper()
                annot_text = f"[{risk_label}] {title}"
                page.add_text_annot(
                    (x, max(0, y - 10)),
                    annot_text,
                    icon="comment"
                )

            doc.save(output_path)
        finally:
            doc.close()

        return output_path
