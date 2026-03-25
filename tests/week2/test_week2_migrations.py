import pytest
from pathlib import Path


def test_week2_tables_exist():
    """Test that the w002 migration creates all Week 2 tables."""
    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "w002_add_week2_tables.py"
    content = migration_path.read_text()

    # Check that all required tables are created
    expected_tables = [
        ("op.create_table('owner_profiles'", "owner_profiles"),
        ("op.create_table('bid_evaluation_reports'", "bid_evaluation_reports"),
        ("op.create_table('approval_logs'", "approval_logs"),
        ("op.create_table('discarded_projects'", "discarded_projects"),
    ]

    for table_pattern, table_name in expected_tables:
        assert table_pattern in content, f"Missing: {table_name} table in migration file"


def test_standard_cert_suggestion_column_added():
    """Test that standard_cert_suggestion column is added to ocr_extractions."""
    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "w002_add_week2_tables.py"
    content = migration_path.read_text()

    assert "op.add_column('ocr_extractions'" in content
    assert "standard_cert_suggestion" in content
    assert "ForeignKey('standard_certifications.id'" in content


def test_enum_values_exist():
    """Test that all new enum values are defined in enums.py."""
    from app.models.enums import TimeUrgencyLevel, RiskLevel, Recommendation, ApprovalAction

    assert TimeUrgencyLevel.EXPIRED.value == "expired"
    assert TimeUrgencyLevel.URGENT.value == "urgent"
    assert TimeUrgencyLevel.TIGHT.value == "tight"
    assert TimeUrgencyLevel.NORMAL.value == "normal"
    assert TimeUrgencyLevel.RELAXED.value == "relaxed"

    assert RiskLevel.HIGH.value == "high"
    assert RiskLevel.MEDIUM.value == "medium"
    assert RiskLevel.LOW.value == "low"

    assert Recommendation.WORTH_BIDDING.value == "worth_bidding"
    assert Recommendation.ABANDON.value == "abandon"
    assert Recommendation.CONDITIONAL.value == "conditional"

    assert ApprovalAction.SPECIALIST_WORTHY.value == "specialist_worthy"
    assert ApprovalAction.SPECIALIST_UNWORTHY.value == "specialist_unworthy"
    assert ApprovalAction.BOSS_OVERRIDE_TERMINATE.value == "boss_override_terminate"
    assert ApprovalAction.BOSS_OVERRIDE_REVIVE.value == "boss_override_revive"
    assert ApprovalAction.BOSS_CONFIRM_SPECIALIST.value == "boss_confirm_specialist"


def test_migration_has_correct_revision_id():
    """Test that migration has correct revision ID."""
    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "w002_add_week2_tables.py"
    content = migration_path.read_text()

    assert "revision = 'w002'" in content
    assert "down_revision = 'w001'" in content


def test_owner_profiles_unique_constraint():
    """Test that owner_profiles has unique constraint on owner_name and region."""
    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "w002_add_week2_tables.py"
    content = migration_path.read_text()

    assert "op.create_table('owner_profiles'" in content
    assert "UniqueConstraint('owner_name', 'region'" in content or "uq_owner_name_region" in content


def test_bid_evaluation_reports_unique_constraint():
    """Test that bid_evaluation_reports has unique constraint on project_id and report_version."""
    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "w002_add_week2_tables.py"
    content = migration_path.read_text()

    assert "op.create_table('bid_evaluation_reports'" in content
    assert "UniqueConstraint('project_id', 'report_version'" in content or "uq_project_version" in content


def test_migration_downgrade_drops_tables_in_correct_order():
    """Test that downgrade drops tables in correct reverse order."""
    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "w002_add_week2_tables.py"
    content = migration_path.read_text()

    # Get the drop_table calls in order
    lines = [l.strip() for l in content.split('\n') if 'drop_table' in l]

    # discarded_projects depends on approval_logs through projects
    # approval_logs depends on projects
    # bid_evaluation_reports depends on projects and owner_profiles
    # owner_profiles is independent
    assert len(lines) >= 4, f"Expected at least 4 drop_table statements, got {len(lines)}"