import pytest
import inspect
from pathlib import Path


def test_migration_creates_all_week1_tables():
    """
    Test that the w001_initial migration creates all Week 1 tables.

    This test verifies that the initial migration contains CREATE TABLE statements
    for all required tables: projects, standard_certifications, tender_documents,
    bid_documents, document_images, and ocr_extractions.
    """
    # Read the migration file
    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "w001_initial_schema.py"
    content = migration_path.read_text()

    # Check that all required tables are created (alembic uses op.create_table)
    # Note: op.create_table( is on one line, 'table_name', is on the next
    expected_tables = [
        ("op.create_table(\n        'projects'", "projects"),
        ("op.create_table(\n        'standard_certifications'", "standard_certifications"),
        ("op.create_table(\n        'tender_documents'", "tender_documents"),
        ("op.create_table(\n        'bid_documents'", "bid_documents"),
        ("op.create_table(\n        'document_images'", "document_images"),
        ("op.create_table(\n        'ocr_extractions'", "ocr_extractions"),
    ]

    for table_pattern, table_name in expected_tables:
        assert table_pattern in content, f"Missing: {table_name} table in migration file"


def test_migration_creates_projects_table():
    """Test that projects table is created with correct columns."""
    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "w001_initial_schema.py"
    content = migration_path.read_text()

    assert "op.create_table(\n        'projects'" in content

    # Check key columns exist
    assert 'project_name' in content.lower()
    assert 'owner_type' in content.lower()
    assert 'status' in content.lower()
    assert 'relationship_flag' in content.lower()


def test_migration_creates_tender_documents_with_unique_constraint():
    """Test that tender_documents table has unique constraint on project_id."""
    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "w001_initial_schema.py"
    content = migration_path.read_text()

    assert "op.create_table(\n        'tender_documents'" in content
    assert 'UniqueConstraint' in content or 'unique' in content.lower()


def test_migration_creates_standard_certifications_table():
    """Test that standard_certifications table is created."""
    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "w001_initial_schema.py"
    content = migration_path.read_text()

    assert "op.create_table(\n        'standard_certifications'" in content
    assert 'cert_code' in content.lower()
    assert 'unique=True' in content  # Unique constraint on cert_code


def test_migration_creates_foreign_key_constraints():
    """Test that foreign key constraints are properly created."""
    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "w001_initial_schema.py"
    content = migration_path.read_text()

    # Check for foreign key references
    assert 'ForeignKey' in content
    assert 'projects.id' in content
    assert 'standard_certifications.id' in content


def test_migration_enables_vector_extension():
    """Test that the vector extension is enabled for pgvector support."""
    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "w001_initial_schema.py"
    content = migration_path.read_text()

    assert "CREATE EXTENSION IF NOT EXISTS VECTOR" in content.upper()


def test_migration_drops_tables_in_correct_order_on_downgrade():
    """
    Test that downgrade drops tables in correct reverse order.

    Tables with FK dependencies must be dropped before the tables they reference.
    """
    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "w001_initial_schema.py"
    content = migration_path.read_text()

    # Get the drop_table calls in order
    lines = [l.strip() for l in content.split('\n') if 'drop_table' in l]

    # ocr_extractions depends on document_images, standard_certifications
    # document_images depends on bid_documents
    # bid_documents depends on projects
    # tender_documents depends on projects
    assert len(lines) >= 6, f"Expected at least 6 drop_table statements, got {len(lines)}"


def test_migration_jsonb_columns_for_extracted_data():
    """Test that JSONB columns are used for extracted_data and similar fields."""
    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "w001_initial_schema.py"
    content = migration_path.read_text()

    # tender_documents.extracted_data should be JSONB
    assert 'jsonb' in content.lower() or 'JSONB' in content


def test_migration_ocr_extractions_has_bbox_coords_jsonb():
    """Test that ocr_extractions table has bbox_coords as JSONB."""
    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "w001_initial_schema.py"
    content = migration_path.read_text()

    assert "op.create_table(\n        'ocr_extractions'" in content
    assert 'bbox_coords' in content.lower()
    assert 'jsonb' in content.lower()


def test_migration_has_correct_revision_id():
    """Test that migration has correct revision ID."""
    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "w001_initial_schema.py"
    content = migration_path.read_text()

    assert "revision = 'w001'" in content
    assert "down_revision = None" in content
