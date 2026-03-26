"""Scoring Index Generator - per Week 3 spec §3.3 C-strategy scoring navigation."""
import re
from sqlalchemy.orm import Session
from app.models.tech_proposal import ScoringIndex


class ScoringIndexGenerator:
    """
    Generates scoring_indexes records for a proposal's sections.

    C-strategy: Expert-friendly navigation index.
    Each scoring item → section → page number → keywords for expert quick-locate.
    """

    CHARS_PER_PAGE = 600  # ~800 chars ≈ 1.5 pages with tables
    COVER_PAGES = 2  # cover + scoring index

    def generate(self, db: Session, project_id: int, sections: list[dict]) -> list[dict]:
        """
        Generate scoring indexes for all sections.

        Args:
            db: SQLAlchemy session
            project_id: Project ID
            sections: List of generated section dicts

        Returns:
            List of scoring index dicts
        """
        indexes = []
        current_page = self.COVER_PAGES + 1  # start after cover + index page

        for section in sections:
            content = section.get('content', '')
            estimated_pages = max(1, len(content) // self.CHARS_PER_PAGE)
            keywords = self._extract_keywords(content)

            idx_record = ScoringIndex(
                project_id=project_id,
                score_item_name=section['section_title'],
                score_weight=section.get('score_weight', 0),
                corresponding_section_id=section.get('section_id'),
                corresponding_section_title=section['section_title'],
                page_number=current_page,
                keyword_matches=keywords,
                is_fully_responded=False
            )
            db.add(idx_record)

            indexes.append({
                'score_item_name': section['section_title'],
                'score_weight': section.get('score_weight', 0),
                'corresponding_section_id': section.get('section_id'),
                'start_page': current_page,
                'end_page': current_page + estimated_pages - 1,
                'keyword_matches': keywords,
                'is_fully_responded': False
            })

            current_page += estimated_pages

        db.commit()
        return indexes

    def _extract_keywords(self, text: str, top_n: int = 5) -> list[str]:
        """Extract top keywords from text (simple frequency-based)."""
        # Remove punctuation and split
        words = re.findall(r'[\u4e00-\u9fff]+', text)  # Chinese words
        # Simple: count occurrences
        freq = {}
        for word in words:
            if len(word) >= 2:
                freq[word] = freq.get(word, 0) + 1
        sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in sorted_words[:top_n]]