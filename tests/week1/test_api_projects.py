import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from app.main import app
from app.dependencies import get_db

# Test database setup - use StaticPool to reuse the same connection for in-memory SQLite
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

# Create all tables using raw SQL (same approach as conftest.py for SQLite compatibility)
with engine.connect() as conn:
    # Create users table first (referenced by projects.created_by)
    conn.execute(text("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(100) NOT NULL UNIQUE,
            email VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    # Create standard_certifications table (using TEXT instead of JSONB for SQLite)
    conn.execute(text("""
        CREATE TABLE standard_certifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cert_code VARCHAR(50) UNIQUE NOT NULL,
            cert_full_name VARCHAR(255) NOT NULL,
            cert_short_name VARCHAR(100),
            aliases TEXT,
            required_keywords TEXT NOT NULL,
            exclude_keywords TEXT NOT NULL,
            cert_number_pattern VARCHAR(100),
            issuing_authority_keywords TEXT,
            category VARCHAR(50),
            validity_years INTEGER,
            is_mandatory_for_food_delivery INTEGER NOT NULL DEFAULT 0,
            is_mandatory_for_property INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    # Create projects table
    conn.execute(text("""
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name VARCHAR(255) NOT NULL,
            project_type VARCHAR(50),
            owner_unit VARCHAR(255),
            owner_type VARCHAR(50) DEFAULT 'enterprise',
            region VARCHAR(100),
            budget_amount NUMERIC(15, 2),
            bid_open_date TIMESTAMP,
            status VARCHAR(50) NOT NULL DEFAULT 'uploaded',
            relationship_flag INTEGER NOT NULL DEFAULT 0,
            generation_mode VARCHAR(20),
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    # Create tender_documents table
    conn.execute(text("""
        CREATE TABLE tender_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            file_path VARCHAR(500),
            file_type VARCHAR(10),
            parsing_status VARCHAR(20) NOT NULL DEFAULT 'pending',
            extracted_data TEXT,
            parsed_by_ai INTEGER NOT NULL DEFAULT 0,
            confirmed_by_human INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_id)
        )
    """))
    # Create bid_documents table
    conn.execute(text("""
        CREATE TABLE bid_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            doc_type VARCHAR(50) NOT NULL,
            file_path VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    # Create document_images table
    conn.execute(text("""
        CREATE TABLE document_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL REFERENCES bid_documents(id) ON DELETE CASCADE,
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            image_path VARCHAR(500),
            page_number INTEGER,
            image_hash VARCHAR(64),
            image_type VARCHAR(50) NOT NULL DEFAULT 'other',
            ocr_status VARCHAR(20) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    # Create ocr_extractions table
    conn.execute(text("""
        CREATE TABLE ocr_extractions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER NOT NULL REFERENCES document_images(id) ON DELETE CASCADE,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            field_name VARCHAR(50) NOT NULL,
            field_value TEXT,
            confidence_score NUMERIC(4, 3),
            normalized_value TEXT,
            standard_cert_id INTEGER REFERENCES standard_certifications(id) ON DELETE SET NULL,
            is_validated INTEGER NOT NULL DEFAULT 0,
            validated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            validation_notes TEXT,
            raw_text TEXT,
            bbox_coords TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conn.commit()

def override_get_db():
    """Override get_db dependency for testing."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Apply the dependency override
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_create_project():
    response = client.post("/api/projects", json={"project_name": "测试项目"})
    assert response.status_code == 200
    assert "id" in response.json()

def test_upload_returns_404_for_nonexistent_project():
    response = client.post("/api/projects/99999/upload", files={"file": ("test.pdf", b"fake", "application/pdf")})
    assert response.status_code == 404