import pytest
import json
from sqlalchemy import text


def test_seed_has_5_certs(session, seed_certs):
    """Should have at least 5 standard certs."""
    result = session.execute(text("SELECT COUNT(*) FROM standard_certifications")).scalar()
    assert result >= 5


def test_business_license_exists(session, seed_certs):
    """Business license cert should exist with correct name."""
    result = session.execute(
        text("SELECT cert_full_name FROM standard_certifications WHERE cert_code = :code"),
        {"code": "BUSINESS-LICENSE"}
    ).fetchone()
    assert result is not None
    assert '营业执照' in result[0]


def test_business_license_has_valid_pattern(session, seed_certs):
    """Business license should have a valid cert number pattern."""
    result = session.execute(
        text("SELECT cert_number_pattern FROM standard_certifications WHERE cert_code = :code"),
        {"code": "BUSINESS-LICENSE"}
    ).fetchone()
    assert result is not None
    assert result[0] is not None
    assert '0-9A-HJ-NPQRTUWXY' in result[0] or '[0-9A-Z]' in result[0]


def test_food_business_license_excludes_production(session, seed_certs):
    """Food business license should exclude production-related keywords."""
    result = session.execute(
        text("SELECT exclude_keywords FROM standard_certifications WHERE cert_code = :code"),
        {"code": "FOOD-BUSINESS-LICENSE"}
    ).fetchone()
    assert result is not None
    excludes = json.loads(result[0]) if isinstance(result[0], str) else result[0]
    assert '生产' in excludes


def test_iso_certs_have_aliases(session, seed_certs):
    """ISO certifications should have aliases for fuzzy matching."""
    result = session.execute(
        text("SELECT aliases FROM standard_certifications WHERE cert_code = :code"),
        {"code": "ISO-9001-2015"}
    ).fetchone()
    assert result is not None
    aliases = json.loads(result[0]) if isinstance(result[0], str) else result[0]
    assert aliases is not None
    assert len(aliases) > 0


def test_iso_14001_exists(session, seed_certs):
    """ISO 14001 certification should exist."""
    result = session.execute(
        text("SELECT cert_code FROM standard_certifications WHERE cert_code = :code"),
        {"code": "ISO-14001-2015"}
    ).fetchone()
    assert result is not None


def test_haccp_exists(session, seed_certs):
    """HACCP certification should exist."""
    result = session.execute(
        text("SELECT cert_code FROM standard_certifications WHERE cert_code = :code"),
        {"code": "HACCP"}
    ).fetchone()
    assert result is not None
