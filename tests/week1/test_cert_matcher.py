import pytest
from app.core.week1_document.cert_matcher import StandardCertMatcher


def test_exact_match_food_business_license(session, seed_certs):
    """'食品经营许可证' should match FOOD-BUSINESS-LICENSE."""
    matcher = StandardCertMatcher(seed_certs)
    result = matcher.suggest_match('食品经营许可证')
    assert result is not None
    assert result['cert_code'] == 'FOOD-BUSINESS-LICENSE'


def test_fuzzy_match_iso_9001(session, seed_certs):
    """'ISO 9001证书' should match ISO-9001-2015."""
    matcher = StandardCertMatcher(seed_certs)
    result = matcher.suggest_match('ISO 9001证书')
    assert result is not None
    assert result['cert_code'] == 'ISO-9001-2015'


def test_fuzzy_match_iso_9001_with_alias(session, seed_certs):
    """'ISO9001认证' should match ISO-9001-2015."""
    matcher = StandardCertMatcher(seed_certs)
    result = matcher.suggest_match('ISO9001认证')
    assert result is not None
    assert result['cert_code'] == 'ISO-9001-2015'


def test_exclude_production_license(session, seed_certs):
    """'食品生产许可证' should NOT match FOOD-BUSINESS-LICENSE."""
    matcher = StandardCertMatcher(seed_certs)
    result = matcher.suggest_match('食品生产许可证')
    # Should not match FOOD-BUSINESS-LICENSE because '生产' is in exclude_keywords
    if result:
        assert result['cert_code'] != 'FOOD-BUSINESS-LICENSE'


def test_low_confidence_returns_none(session, seed_certs):
    """Garbage text should return None."""
    matcher = StandardCertMatcher(seed_certs)
    result = matcher.suggest_match('这是什么东西')
    assert result is None


def test_haccp_exact_match(session, seed_certs):
    """'HACCP认证' should match HACCP."""
    matcher = StandardCertMatcher(seed_certs)
    result = matcher.suggest_match('HACCP认证')
    assert result is not None
    assert result['cert_code'] == 'HACCP'


def test_business_license_match(session, seed_certs):
    """'营业执照' should match BUSINESS-LICENSE."""
    matcher = StandardCertMatcher(seed_certs)
    result = matcher.suggest_match('营业执照')
    assert result is not None
    assert result['cert_code'] == 'BUSINESS-LICENSE'


def test_confidence_above_threshold(session, seed_certs):
    """Match with high confidence should return confidence >= 0.5."""
    matcher = StandardCertMatcher(seed_certs)
    result = matcher.suggest_match('食品经营许可证')
    assert result is not None
    assert result['confidence'] >= 0.5
