import pytest
from datetime import date, timedelta
from app.core.week2_evaluation.qualification_matcher import QualificationMatcher

class TestExactMatcherR1Rules:
    """R1 Life-or-Death boundary tests."""

    def test_missing_mandatory_cert_returns_fatal(self, db_session, seed_standard_certs):
        """Required cert not in OCR extractions → fatal_missing."""
        matcher = QualificationMatcher(db_session, project_id=1)
        result = matcher.exact_match_evaluation()
        # FOOD-BUSINESS-LICENSE is mandatory but not in OCR → fatal
        missing = [m for m in result['missing_mandatory_certs'] if m['cert_code'] == 'FOOD-BUSINESS-LICENSE']
        assert len(missing) > 0
        assert missing[0]['reason'] == 'missing'

    def test_expired_cert_returns_fatal(self, db_session, seed_standard_certs, seed_expired_cert):
        """Cert found but valid_until < bid_open_date → expired (fatal)."""
        matcher = QualificationMatcher(db_session, project_id=1)
        result = matcher.exact_match_evaluation()
        # The expired cert should be in fatal_missing with reason='expired'
        expired = [m for m in result['missing_mandatory_certs'] if m.get('reason') == 'expired']
        assert len(expired) > 0

    def test_exclude_keyword_blocks_wrong_cert(self, db_session, seed_standard_certs, seed_wrong_cert_with_exclude):
        """Food production cert used as food business → REJECTED (exclude keyword safeguard)."""
        matcher = QualificationMatcher(db_session, project_id=1)
        result = matcher.exact_match_evaluation()
        # The wrong cert should NOT be in matched_certs, and FOOD-BUSINESS-LICENSE should be missing
        matched_codes = [m['cert_code'] for m in result['matched_certs']]
        assert 'FOOD-BUSINESS-LICENSE' not in matched_codes

    def test_level_1_not_matched_for_level_2_requirement(self, db_session, seed_standard_certs):
        """'Construction Grade 2' requirement should NOT match 'Grade 1' cert."""
        matcher = QualificationMatcher(db_session, project_id=1)
        # Set up: tender requires CONSTRUCTION-GENERAL-2 (level 2)
        # But OCR only has CONSTRUCTION-GENERAL-1 (level 1)
        result = matcher.exact_match_evaluation()
        # Level mismatch should result in not matched
        matched_codes = [m['cert_code'] for m in result['matched_certs']]
        assert 'CONSTRUCTION-GENERAL-2' not in matched_codes

    def test_score_calculation_with_missing(self, db_session, seed_standard_certs):
        """Score = matched_mandatory / total_mandatory * 100."""
        matcher = QualificationMatcher(db_session, project_id=1)
        result = matcher.exact_match_evaluation()
        assert 'qualification_match_score' in result
        assert isinstance(result['qualification_match_score'], int)

    def test_all_valid_returns_100_score(self, db_session, seed_all_valid_certs):
        """All mandatory certs valid and matched → score=100, is_qualification_pass=True."""
        matcher = QualificationMatcher(db_session, project_id=1)
        result = matcher.exact_match_evaluation()
        assert result['qualification_match_score'] == 100
        assert result['is_qualification_pass'] is True
        assert len(result['missing_mandatory_certs']) == 0