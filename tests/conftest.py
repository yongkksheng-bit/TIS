import pytest
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import json


# Test database URL (SQLite for testing)
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def engine():
    """Create a test engine for each test."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
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
    yield engine


@pytest.fixture(scope="function")
def session(engine):
    """Create a new database session for a test."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def _parse_json_field(value):
    """Parse JSON field from database."""
    if value is None:
        return []
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return [value]
    return value


@pytest.fixture
def seed_certs(session):
    """Seed standard certifications and return as list of dicts."""
    from scripts.seed_standard_certs import SEED_DATA

    certs_list = []
    for data in SEED_DATA:
        # Convert lists to JSON strings for storage
        cert_data = {}
        for key, value in data.items():
            if key in ['aliases', 'required_keywords', 'exclude_keywords', 'issuing_authority_keywords']:
                cert_data[key] = json.dumps(value) if value else None
            else:
                cert_data[key] = value

        # Check if exists
        result = session.execute(
            text("SELECT id FROM standard_certifications WHERE cert_code = :code"),
            {"code": cert_data['cert_code']}
        ).fetchone()

        if not result:
            # Build column names and values for INSERT
            columns = list(cert_data.keys())
            values = list(cert_data.values())
            placeholders = [f":{col}" for col in columns]
            insert_sql = text(f"""
                INSERT INTO standard_certifications ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
            """)
            session.execute(insert_sql, dict(zip(columns, values)))

        # Fetch the inserted cert and convert to dict
        row = session.execute(
            text("SELECT * FROM standard_certifications WHERE cert_code = :code"),
            {"code": cert_data['cert_code']}
        ).fetchone()
        if row:
            # Convert row to dict
            cert_dict = {
                'id': row[0],
                'cert_code': row[1],
                'cert_full_name': row[2],
                'cert_short_name': row[3],
                'aliases': _parse_json_field(row[4]),
                'required_keywords': _parse_json_field(row[5]),
                'exclude_keywords': _parse_json_field(row[6]),
                'cert_number_pattern': row[7],
                'issuing_authority_keywords': _parse_json_field(row[8]),
                'category': row[9],
                'validity_years': row[10],
                'is_mandatory_for_food_delivery': bool(row[11]),
                'is_mandatory_for_property': bool(row[12]),
                'is_active': bool(row[13]),
            }
            certs_list.append(cert_dict)

    session.commit()
    return certs_list


@pytest.fixture
def check_tables_exist():
    """
    Fixture that checks if all Week 1 tables are created by the migration.

    Returns a function that checks if table creation statements exist in the migration.
    """
    def _check_tables(sql_output):
        expected_tables = [
            'CREATE TABLE projects',
            'CREATE TABLE standard_certifications',
            'CREATE TABLE tender_documents',
            'CREATE TABLE bid_documents',
            'CREATE TABLE document_images',
            'CREATE TABLE ocr_extractions',
        ]
        results = {}
        for table in expected_tables:
            results[table] = table.upper() in sql_output.upper()
        return results

    return _check_tables
