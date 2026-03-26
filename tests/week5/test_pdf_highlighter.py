"""TDD tests for BidPDFHighlighter."""
import pytest
import tempfile
import os
import fitz


class TestBidPDFHighlighter:
    """Tests for BidPDFHighlighter using PyMuPDF."""

    def test_highlight_keywords_creates_annotated_file(self):
        """BidPDFHighlighter.highlight_keywords creates an annotated output PDF."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_pdf = os.path.join(tmpdir, "input.pdf")
            output_pdf = os.path.join(tmpdir, "output_annotated.pdf")

            # Create minimal 1-page A4 PDF with Chinese text using PyMuPDF
            doc = fitz.open()
            page = doc.new_page(width=595, height=842)  # A4
            page.insert_text((100, 100), "ISO22000食品认证证书", fontsize=12)
            doc.save(input_pdf)
            doc.close()

            # Apply keyword highlights
            from app.core.week5_formal_review.pdf_highlighter import BidPDFHighlighter
            highlighter = BidPDFHighlighter(input_pdf)
            result = highlighter.highlight_keywords(input_pdf, output_pdf, ["ISO22000", "认证"])
            assert os.path.exists(result)

    def test_apply_highlights_with_coords_creates_file(self):
        """BidPDFHighlighter.apply_highlights creates an annotated PDF at specified coordinates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_pdf = os.path.join(tmpdir, "input.pdf")
            output_pdf = os.path.join(tmpdir, "output_highlights.pdf")

            # Create minimal PDF
            doc = fitz.open()
            page = doc.new_page(width=595, height=842)
            page.insert_text((100, 100), "Test Document", fontsize=12)
            doc.save(input_pdf)
            doc.close()

            # Apply highlights at specified coordinates
            from app.core.week5_formal_review.pdf_highlighter import BidPDFHighlighter
            highlighter = BidPDFHighlighter(input_pdf)
            review_items = [
                {
                    "check_title": "资质过期",
                    "risk_level": "fatal",
                    "pdf_highlight_coords": {"page": 1, "x": 50, "y": 50, "width": 200, "height": 30}
                }
            ]
            result = highlighter.apply_highlights(review_items, output_pdf)
            assert os.path.exists(result)

    def test_color_for_risk_fatal_is_red(self):
        """_color_for_risk('fatal') returns approximately (1, 0, 0) = red."""
        from app.core.week5_formal_review.pdf_highlighter import BidPDFHighlighter
        color = BidPDFHighlighter._color_for_risk('fatal')
        assert color == (1, 0, 0)  # RGB red

    def test_color_for_risk_warning_is_yellow(self):
        """_color_for_risk('warning') returns approximately (1, 0.8, 0) = yellow."""
        from app.core.week5_formal_review.pdf_highlighter import BidPDFHighlighter
        color = BidPDFHighlighter._color_for_risk('warning')
        assert color == (1, 0.8, 0)  # RGB yellow

    def test_color_for_risk_info_is_green(self):
        """_color_for_risk('info') returns approximately (0, 1, 0) = green."""
        from app.core.week5_formal_review.pdf_highlighter import BidPDFHighlighter
        color = BidPDFHighlighter._color_for_risk('info')
        assert color == (0, 1, 0)  # RGB green
