"""Standard certification matcher for OCR text.

This module provides fuzzy matching between OCR-extracted text and
standard certification library using lightweight string matching.
"""
import json
import re
from difflib import SequenceMatcher
from typing import Optional, List, Dict, Any, Union
from sqlalchemy.orm import Session

from app.models.standard import StandardCertification

# Minimum confidence threshold for returning a match
CONFIDENCE_THRESHOLD = 0.5


class StandardCertMatcher:
    """Matcher for OCR text against standard certifications."""

    def __init__(self, db_or_certs: Union[Session, List[Dict[str, Any]]]):
        """Initialize matcher with database session or list of cert dicts.

        Args:
            db_or_certs: Either a SQLAlchemy Session or a list of cert dictionaries
        """
        if isinstance(db_or_certs, Session):
            self.db = db_or_certs
            self._cert_cache: List[Dict[str, Any]] = []
            self._load_certs_from_db()
        else:
            self.db = None
            self._cert_cache = db_or_certs

    def _load_certs_from_db(self) -> None:
        """Load all active standard certifications into memory from DB."""
        certs = self.db.query(StandardCertification).filter_by(is_active=True).all()
        self._cert_cache = []
        for cert in certs:
            self._cert_cache.append(self._cert_to_dict(cert))

    def _cert_to_dict(self, cert: StandardCertification) -> Dict[str, Any]:
        """Convert StandardCertification model to dict with parsed JSON fields.

        Args:
            cert: StandardCertification model instance

        Returns:
            Dict with cert fields and parsed JSON fields
        """
        def parse_json_field(value):
            if value is None:
                return []
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return [value]
            return value

        return {
            'id': cert.id,
            'cert_code': cert.cert_code,
            'cert_full_name': cert.cert_full_name,
            'cert_short_name': cert.cert_short_name or '',
            'aliases': parse_json_field(cert.aliases),
            'required_keywords': parse_json_field(cert.required_keywords),
            'exclude_keywords': parse_json_field(cert.exclude_keywords),
        }

    def _calculate_fuzzy_score(self, text: str, pattern: str) -> float:
        """Calculate fuzzy match score between two strings.

        Args:
            text: Input text (e.g., OCR result)
            pattern: Pattern to match against (e.g., alias)

        Returns:
            Similarity score between 0 and 1
        """
        text = text.lower()
        pattern = pattern.lower()
        return SequenceMatcher(None, text, pattern).ratio()

    def _check_exclude_keywords(self, text: str, cert_dict: Dict[str, Any]) -> bool:
        """Check if text contains any exclude keywords for the certification.

        Args:
            text: Input text to check
            cert_dict: Certification dict with exclude_keywords

        Returns:
            True if text contains exclude keyword (should exclude), False otherwise
        """
        text_lower = text.lower()
        for keyword in cert_dict.get('exclude_keywords', []):
            if keyword.lower() in text_lower:
                return True
        return False

    def _calculate_match_score(self, ocr_text: str, cert_dict: Dict[str, Any]) -> float:
        """Calculate match score between OCR text and a certification.

        Args:
            ocr_text: Input text from OCR
            cert_dict: Certification dict

        Returns:
            Match score between 0 and 1, or 0 if no match
        """
        ocr_lower = ocr_text.lower()
        score = 0.0
        matched_alias = False

        # 1. Exact match on full name (highest weight)
        if ocr_text == cert_dict['cert_full_name']:
            return 1.0
        elif cert_dict['cert_full_name'].lower() in ocr_lower or ocr_lower in cert_dict['cert_full_name'].lower():
            score = max(score, 0.9)

        # 2. Exact match on short name
        if cert_dict['cert_short_name']:
            if ocr_text == cert_dict['cert_short_name']:
                score = max(score, 0.9)
            elif cert_dict['cert_short_name'].lower() in ocr_lower or ocr_lower in cert_dict['cert_short_name'].lower():
                score = max(score, 0.8)

        # 3. Check aliases for exact or substring match
        for alias in cert_dict.get('aliases', []):
            if not alias:
                continue
            alias_lower = alias.lower()
            # Exact alias match
            if ocr_lower == alias_lower:
                return 0.95  # Very high score for exact alias match
            # Substring match
            elif alias_lower in ocr_lower or ocr_lower in alias_lower:
                score = max(score, 0.8)
                matched_alias = True
                break
            # Fuzzy match (only if no better match found yet)
            elif score < 0.6:
                fuzzy_score = self._calculate_fuzzy_score(ocr_text, alias)
                if fuzzy_score > 0.6:
                    score = max(score, fuzzy_score * 0.7)

        # 4. If we have a reasonable score from name/alias, return it
        if score >= 0.5:
            return score

        # 5. Check required_keywords as fallback
        required = cert_dict.get('required_keywords', [])
        if required:
            for keyword in required:
                if keyword.lower() in ocr_lower:
                    score = max(score, 0.5)
                    break

        return score

    def suggest_match(self, ocr_text: str) -> Optional[Dict[str, Any]]:
        """Suggest a standard certification match for OCR text.

        This is SUGGESTION ONLY - it does not set standard_cert_id on any record.

        Args:
            ocr_text: Text extracted from OCR (e.g., "食品经营许可证")

        Returns:
            Dict with 'cert_id', 'cert_code', 'confidence' if match found,
            or None if confidence is below threshold or no match found.
        """
        if not ocr_text or not ocr_text.strip():
            return None

        ocr_text = ocr_text.strip()
        best_match: Optional[Dict[str, Any]] = None
        best_score = 0.0

        for cert_dict in self._cert_cache:
            # First check exclude keywords - if found, skip this cert
            if self._check_exclude_keywords(ocr_text, cert_dict):
                continue

            # Calculate match score
            score = self._calculate_match_score(ocr_text, cert_dict)

            # Update best match
            if score > best_score:
                best_score = score
                best_match = {
                    'cert_id': cert_dict['id'],
                    'cert_code': cert_dict['cert_code'],
                    'confidence': round(score, 2)
                }

        # Return None if below threshold
        if best_match and best_match['confidence'] >= CONFIDENCE_THRESHOLD:
            return best_match

        return None
