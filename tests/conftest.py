import pytest
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import json
from datetime import datetime, timedelta


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
                relation_identifier VARCHAR(50),
                differentiation_guidance VARCHAR(1000),
                generation_mode VARCHAR(20),
                is_retender INTEGER NOT NULL DEFAULT 0,
                parent_project_id INTEGER,
                plan_code VARCHAR(50),
                agency_project_code VARCHAR(100),
                is_deleted INTEGER NOT NULL DEFAULT 0,
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
                plan_code VARCHAR(50),
                agency_project_code VARCHAR(100),
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
        # Create owner_profiles table
        conn.execute(text("""
            CREATE TABLE owner_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_name VARCHAR(255) NOT NULL,
                owner_type VARCHAR(50),
                region VARCHAR(100),
                cooperation_count INTEGER DEFAULT 0,
                last_cooperation_date DATE,
                relationship_level VARCHAR(20) DEFAULT 'none',
                avg_winning_discount NUMERIC(5, 2),
                preferred_styles TEXT,
                common_requirements TEXT,
                blacklist_flags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(owner_name, region)
            )
        """))
        # Create bid_evaluation_reports table
        conn.execute(text("""
            CREATE TABLE bid_evaluation_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                report_version INTEGER DEFAULT 1,
                qualification_match_score INTEGER,
                missing_mandatory_certs TEXT,
                missing_optional_certs TEXT,
                matched_certs_detail TEXT,
                days_until_bid_open INTEGER,
                time_urgency_level VARCHAR(20),
                is_time_sufficient INTEGER,
                owner_profile_id INTEGER REFERENCES owner_profiles(id),
                relationship_index INTEGER,
                is_new_owner INTEGER,
                estimated_cost NUMERIC(15, 2),
                suggested_price_range_low NUMERIC(15, 2),
                suggested_price_range_high NUMERIC(15, 2),
                cost_estimate_confidence VARCHAR(20),
                overall_win_probability NUMERIC(5, 4),
                risk_level VARCHAR(20),
                fatal_risks TEXT,
                warning_risks TEXT,
                recommendation VARCHAR(20),
                recommendation_reason VARCHAR(500),
                generated_by VARCHAR(50) DEFAULT 'system',
                confirmed_by_specialist INTEGER DEFAULT 0,
                specialist_decision VARCHAR(20),
                specialist_notes VARCHAR(500),
                confirmed_at TIMESTAMP,
                overridden_by_boss INTEGER DEFAULT 0,
                boss_override_reason VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project_id, report_version),
                CHECK (qualification_match_score BETWEEN 0 AND 100),
                CHECK (relationship_index BETWEEN 0 AND 100)
            )
        """))
        # Create approval_logs table
        conn.execute(text("""
            CREATE TABLE approval_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                action_type VARCHAR(50) NOT NULL,
                actor_role VARCHAR(50) NOT NULL,
                actor_id INTEGER REFERENCES users(id),
                reason_text TEXT,
                original_status VARCHAR(50),
                new_status VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        # Create discarded_projects table
        conn.execute(text("""
            CREATE TABLE discarded_projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                original_evaluation_report_id INTEGER REFERENCES bid_evaluation_reports(id),
                discarded_by VARCHAR(50) NOT NULL,
                discard_reason TEXT,
                discard_stage VARCHAR(50),
                can_be_revived INTEGER DEFAULT 1,
                revived_at TIMESTAMP,
                revived_by INTEGER REFERENCES users(id),
                revived_to_project_id INTEGER REFERENCES projects(id),
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


@pytest.fixture
def db_session(session):
    """Alias for session to match test naming convention."""
    return session


@pytest.fixture
def seed_project_with_tender(session):
    """Create a project with id=1 and tender document with qualification requirements."""
    from datetime import datetime, timedelta

    # Create user first
    session.execute(text("""
        INSERT INTO users (id, username, email) VALUES (1, 'testuser', 'test@test.com')
    """))

    # Create project with bid_open_date = today + 30 days
    bid_date = datetime.now() + timedelta(days=30)
    session.execute(text("""
        INSERT INTO projects (id, project_name, project_type, bid_open_date, status, created_by)
        VALUES (1, 'Test Project', 'food', :bid_date, 'uploaded', 1)
    """), {"bid_date": bid_date})

    # Create tender document with qualification requirements
    # FOOD-BUSINESS-LICENSE is mandatory, ISO-9001-2015 is optional
    tender_data = json.dumps({
        'qualification_requirements': [
            {'cert_code': 'FOOD-BUSINESS-LICENSE', 'is_mandatory': True},
            {'cert_code': 'ISO-9001-2015', 'is_mandatory': False},
        ]
    })
    session.execute(text("""
        INSERT INTO tender_documents (project_id, parsing_status, extracted_data, parsed_by_ai, confirmed_by_human)
        VALUES (1, 'completed', :data, 1, 1)
    """), {"data": tender_data})

    # Create bid document and image for OCR extractions
    session.execute(text("""
        INSERT INTO bid_documents (id, project_id, doc_type) VALUES (1, 1, 'qualification')
    """))
    session.execute(text("""
        INSERT INTO document_images (id, document_id, project_id, image_type, ocr_status)
        VALUES (1, 1, 1, 'certification', 'success')
    """))

    session.commit()
    return session


@pytest.fixture
def seed_standard_certs(seed_project_with_tender):
    """Seed FOOD-BUSINESS-LICENSE and ISO-9001 certs for week 2 tests."""
    session = seed_project_with_tender

    certs = [
        {
            'cert_code': 'FOOD-BUSINESS-LICENSE',
            'cert_full_name': '食品经营许可证',
            'required_keywords': json.dumps(['食品经营', '许可证']),
            'exclude_keywords': json.dumps(['生产', '小作坊']),
            'is_active': 1
        },
        {
            'cert_code': 'ISO-9001-2015',
            'cert_full_name': '质量管理体系认证',
            'required_keywords': json.dumps(['质量管理体系', '认证']),
            'exclude_keywords': json.dumps([]),
            'is_active': 1
        },
    ]

    for cert_data in certs:
        session.execute(text("""
            INSERT INTO standard_certifications (cert_code, cert_full_name, required_keywords, exclude_keywords, is_active)
            VALUES (:cert_code, :cert_full_name, :required_keywords, :exclude_keywords, :is_active)
        """), cert_data)

    session.commit()
    return session


@pytest.fixture
def seed_expired_cert(seed_standard_certs):
    """Add OCR extraction for FOOD-BUSINESS-LICENSE that expired 1 day before bid open."""
    session = seed_standard_certs

    # Get the cert id
    row = session.execute(
        text("SELECT id FROM standard_certifications WHERE cert_code = 'FOOD-BUSINESS-LICENSE'")
    ).fetchone()
    cert_id = row[0]

    # Get bid_open_date and calculate expired date
    row = session.execute(
        text("SELECT bid_open_date FROM projects WHERE id = 1")
    ).fetchone()
    bid_date = datetime.fromisoformat(row[0]) if isinstance(row[0], str) else row[0].replace(tzinfo=None)
    expired_date = bid_date - timedelta(days=1)

    session.execute(text("""
        INSERT INTO ocr_extractions (image_id, project_id, field_name, field_value, normalized_value, standard_cert_id, is_validated)
        VALUES (1, 1, 'valid_until', :expired_date, :expired_date, :cert_id, 1)
    """), {"expired_date": expired_date.strftime('%Y-%m-%d'), "cert_id": cert_id})

    session.commit()
    return session


@pytest.fixture
def seed_wrong_cert_with_exclude(seed_standard_certs):
    """Add OCR extraction that has cert_id of FOOD-BUSINESS but name contains '生产' (exclude keyword)."""
    session = seed_standard_certs

    # Get the cert id
    row = session.execute(
        text("SELECT id FROM standard_certifications WHERE cert_code = 'FOOD-BUSINESS-LICENSE'")
    ).fetchone()
    cert_id = row[0]

    # Insert OCR extraction with wrong cert name containing exclude keyword
    session.execute(text("""
        INSERT INTO ocr_extractions (image_id, project_id, field_name, field_value, normalized_value, standard_cert_id, is_validated)
        VALUES (1, 1, 'cert_name', '食品生产许可证', '食品生产许可证', :cert_id, 1)
    """), {"cert_id": cert_id})

    session.commit()
    return session


@pytest.fixture
def seed_all_valid_certs(seed_standard_certs):
    """Add OCR extraction for all certs that are valid (not expired)."""
    session = seed_standard_certs

    # Get cert ids
    food_cert_row = session.execute(
        text("SELECT id FROM standard_certifications WHERE cert_code = 'FOOD-BUSINESS-LICENSE'")
    ).fetchone()
    iso_cert_row = session.execute(
        text("SELECT id FROM standard_certifications WHERE cert_code = 'ISO-9001-2015'")
    ).fetchone()

    # Get bid_open_date and calculate valid dates (far future)
    row = session.execute(
        text("SELECT bid_open_date FROM projects WHERE id = 1")
    ).fetchone()
    bid_date = datetime.fromisoformat(row[0]) if isinstance(row[0], str) else row[0].replace(tzinfo=None)
    valid_date = bid_date + timedelta(days=365)

    # Insert valid FOOD-BUSINESS-LICENSE
    if food_cert_row:
        session.execute(text("""
            INSERT INTO ocr_extractions (image_id, project_id, field_name, field_value, normalized_value, standard_cert_id, is_validated)
            VALUES (1, 1, 'cert_name', '食品经营许可证', '食品经营许可证', :cert_id, 1)
        """), {"cert_id": food_cert_row[0]})

        session.execute(text("""
            INSERT INTO ocr_extractions (image_id, project_id, field_name, field_value, normalized_value, standard_cert_id, is_validated)
            VALUES (1, 1, 'valid_until', :valid_date, :valid_date, :cert_id, 1)
        """), {"valid_date": valid_date.strftime('%Y-%m-%d'), "cert_id": food_cert_row[0]})

    session.commit()
    return session
