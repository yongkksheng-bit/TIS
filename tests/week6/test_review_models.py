"""TDD tests for Week 6 review SQLAlchemy models."""
import pytest
from decimal import Decimal
from datetime import date, datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db_session():
    """In-memory SQLite session for model testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(100))"))
        conn.execute(text("""CREATE TABLE projects (
            id INTEGER PRIMARY KEY, project_name VARCHAR(255), status VARCHAR(50),
            budget_amount NUMERIC(15,2), bid_open_date TIMESTAMP
        )"""))
        conn.execute(text("""CREATE TABLE knowledge_chunks (
            id INTEGER PRIMARY KEY, chunk_type VARCHAR(50), content TEXT,
            content_vector TEXT, chunk_metadata TEXT, source_project_id INTEGER,
            is_deprecated INTEGER, created_at TIMESTAMP, updated_at TIMESTAMP
        )"""))
        conn.execute(text("""CREATE TABLE formal_review_items (
            id INTEGER PRIMARY KEY, project_id INTEGER, source_type VARCHAR(50),
            parent_item_id INTEGER, check_category VARCHAR(50), check_title VARCHAR(255),
            check_description TEXT, reference_clause TEXT, system_status VARCHAR(20),
            system_evidence TEXT, specialist_status VARCHAR(20) DEFAULT 'pending',
            specialist_notes TEXT, corrected_evidence TEXT, confirmed_by INTEGER,
            confirmed_at TIMESTAMP, pdf_highlight_coords TEXT, risk_level VARCHAR(20),
            created_at TIMESTAMP, updated_at TIMESTAMP
        )"""))
        conn.execute(text("""CREATE TABLE abandoned_drafts (
            id INTEGER PRIMARY KEY, project_id INTEGER, termination_stage VARCHAR(50),
            tech_proposal_path VARCHAR(500), business_proposal_path VARCHAR(500),
            pricing_decision_id INTEGER, termination_reason TEXT, termination_by INTEGER,
            can_be_revived INTEGER DEFAULT 1, archived_at TIMESTAMP, revived_at TIMESTAMP,
            revived_to_project_id INTEGER
        )"""))
        conn.execute(text("""CREATE TABLE bid_outcomes (
            id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL,
            outcome_status VARCHAR(20) NOT NULL, outcome_date DATE NOT NULL,
            final_bid_price NUMERIC(15, 2) NOT NULL, winning_price NUMERIC(15, 2),
            winning_unit VARCHAR(255), our_price_rank INTEGER,
            disqualification_reason TEXT, disqualification_type VARCHAR(50),
            related_review_item_id INTEGER, is_manual_error INTEGER NOT NULL DEFAULT 0,
            review_analysis TEXT, reviewed_by INTEGER, reviewed_at TIMESTAMP,
            review_notes TEXT, created_at TIMESTAMP
        )"""))
        conn.execute(text("""CREATE TABLE winning_dna (
            id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL,
            source_chunk_id INTEGER, dna_type VARCHAR(50) NOT NULL,
            score_contribution INTEGER NOT NULL, scoring_item_matched VARCHAR(255),
            owner_type VARCHAR(50), project_scale VARCHAR(50),
            reused_in_projects TEXT DEFAULT '[]', reuse_success_rate NUMERIC(5, 2),
            extracted_at TIMESTAMP, confirmed_by INTEGER
        )"""))
        conn.execute(text("""CREATE TABLE disqualification_traps (
            id INTEGER PRIMARY KEY, trap_code VARCHAR(50) NOT NULL UNIQUE,
            trap_category VARCHAR(50) NOT NULL, trap_title VARCHAR(255) NOT NULL,
            trap_description TEXT NOT NULL, detection_method TEXT,
            first_occurrence_project_id INTEGER, occurrence_count INTEGER NOT NULL DEFAULT 1,
            prevention_checklist_item TEXT, is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP
        )"""))
        conn.execute(text("""CREATE TABLE draft_revivals (
            id INTEGER PRIMARY KEY, abandoned_draft_id INTEGER NOT NULL,
            new_project_id INTEGER NOT NULL, revival_type VARCHAR(50) NOT NULL,
            revived_content TEXT, adaptation_notes TEXT, revived_by INTEGER,
            revived_at TIMESTAMP, is_successful INTEGER
        )"""))
        conn.execute(text("""CREATE TABLE knowledge_evolution_logs (
            id INTEGER PRIMARY KEY, chunk_id INTEGER NOT NULL,
            action_type VARCHAR(50) NOT NULL, project_id INTEGER,
            old_quality_score INTEGER, new_quality_score INTEGER,
            reason TEXT, created_at TIMESTAMP
        )"""))
        conn.execute(text("INSERT INTO users (id, username) VALUES (1, 'boss')"))
        conn.execute(text("INSERT INTO projects (id, project_name, status) VALUES (1, 'Test Project', 'awaiting_review')"))
        conn.execute(text("INSERT INTO projects (id, project_name, status) VALUES (2, 'Test Project 2', 'awaiting_review')"))
        conn.execute(text("INSERT INTO knowledge_chunks (id, chunk_type, content, chunk_metadata) VALUES (1, 'case', 'Test content', '{}')"))
        conn.execute(text("INSERT INTO formal_review_items (id, project_id, source_type, check_category, check_title, system_status, risk_level) VALUES (1, 1, 'system_parsed', 'qualification_validity', 'Test', 'passed', 'info')"))
        conn.execute(text("INSERT INTO abandoned_drafts (id, project_id, can_be_revived) VALUES (1, 1, 1)"))
        conn.commit()
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestBidOutcomeModel:
    def test_create_bid_outcome_win(self, db_session):
        """BidOutcome can be created with win status."""
        from app.models.review import BidOutcome
        outcome = BidOutcome(
            project_id=1,
            outcome_status='win',
            outcome_date=date(2026, 1, 15),
            final_bid_price=Decimal('150000.00'),
            winning_price=Decimal('145000.00'),
            winning_unit='万元',
            our_price_rank=1,
        )
        db_session.add(outcome)
        db_session.commit()
        loaded = db_session.get(BidOutcome, outcome.id)
        assert loaded.outcome_status == 'win'
        assert loaded.our_price_rank == 1

    def test_create_bid_outcome_disqualified(self, db_session):
        """BidOutcome can be created with disqualified status."""
        from app.models.review import BidOutcome
        outcome = BidOutcome(
            project_id=1,
            outcome_status='disqualified',
            outcome_date=date(2026, 1, 15),
            final_bid_price=Decimal('150000.00'),
            disqualification_reason='Missing signature page',
            disqualification_type='fatal_formal',
        )
        db_session.add(outcome)
        db_session.commit()
        loaded = db_session.get(BidOutcome, outcome.id)
        assert loaded.outcome_status == 'disqualified'
        assert loaded.disqualification_type == 'fatal_formal'

    def test_query_by_project_id(self, db_session):
        """BidOutcome can be queried by project_id."""
        from app.models.review import BidOutcome
        outcome = BidOutcome(
            project_id=1,
            outcome_status='win',
            outcome_date=date(2026, 1, 15),
            final_bid_price=Decimal('150000.00'),
        )
        db_session.add(outcome)
        db_session.commit()
        results = db_session.query(BidOutcome).filter(BidOutcome.project_id == 1).all()
        assert len(results) == 1
        assert results[0].outcome_status == 'win'

    def test_outcome_status_filter(self, db_session):
        """BidOutcome can be filtered by outcome_status."""
        from app.models.review import BidOutcome
        outcome1 = BidOutcome(
            project_id=1,
            outcome_status='win',
            outcome_date=date(2026, 1, 15),
            final_bid_price=Decimal('150000.00'),
        )
        outcome2 = BidOutcome(
            project_id=2,
            outcome_status='lose',
            outcome_date=date(2026, 1, 15),
            final_bid_price=Decimal('160000.00'),
        )
        db_session.add(outcome1)
        db_session.add(outcome2)
        db_session.commit()
        wins = db_session.query(BidOutcome).filter(BidOutcome.outcome_status == 'win').all()
        assert len(wins) == 1
        assert wins[0].project_id == 1

    def test_is_manual_error_defaults_false(self, db_session):
        """is_manual_error defaults to False."""
        from app.models.review import BidOutcome
        outcome = BidOutcome(
            project_id=1,
            outcome_status='win',
            outcome_date=date(2026, 1, 15),
            final_bid_price=Decimal('150000.00'),
        )
        db_session.add(outcome)
        db_session.commit()
        loaded = db_session.get(BidOutcome, outcome.id)
        assert loaded.is_manual_error is False

    def test_review_analysis_json(self, db_session):
        """review_analysis stores JSON dict."""
        from app.models.review import BidOutcome
        analysis = {"win_factors": ["price", "quality"], "lose_factors": []}
        outcome = BidOutcome(
            project_id=1,
            outcome_status='win',
            outcome_date=date(2026, 1, 15),
            final_bid_price=Decimal('150000.00'),
            review_analysis=analysis,
        )
        db_session.add(outcome)
        db_session.commit()
        loaded = db_session.get(BidOutcome, outcome.id)
        assert loaded.review_analysis["win_factors"][0] == "price"


class TestWinningDNAModel:
    def test_create_winning_dna(self, db_session):
        """WinningDNA can be created linked to project and knowledge_chunk."""
        from app.models.review import WinningDNA
        dna = WinningDNA(
            project_id=1,
            source_chunk_id=1,
            dna_type='winning_price_strategy',
            score_contribution=8,
            scoring_item_matched='Price competitiveness',
        )
        db_session.add(dna)
        db_session.commit()
        loaded = db_session.get(WinningDNA, dna.id)
        assert loaded.dna_type == 'winning_price_strategy'
        assert loaded.score_contribution == 8

    def test_reused_in_projects_defaults_empty_list(self, db_session):
        """reused_in_projects defaults to empty list."""
        from app.models.review import WinningDNA
        dna = WinningDNA(
            project_id=1,
            dna_type='high_score_response',
            score_contribution=7,
        )
        db_session.add(dna)
        db_session.commit()
        loaded = db_session.get(WinningDNA, dna.id)
        assert loaded.reused_in_projects == '[]'

    def test_query_by_project_id(self, db_session):
        """WinningDNA can be queried by project_id."""
        from app.models.review import WinningDNA
        dna = WinningDNA(
            project_id=1,
            dna_type='format_excellence',
            score_contribution=9,
        )
        db_session.add(dna)
        db_session.commit()
        results = db_session.query(WinningDNA).filter(WinningDNA.project_id == 1).all()
        assert len(results) == 1


class TestDisqualificationTrapModel:
    def test_create_trap(self, db_session):
        """DisqualificationTrap can be created with unique trap_code."""
        from app.models.review import DisqualificationTrap
        trap = DisqualificationTrap(
            trap_code='NO_SIGNATURE_PAGE',
            trap_category='signature',
            trap_title='Missing Signature Page',
            trap_description='Signature page was not found in the submitted document',
            detection_method='PDF text extraction',
            occurrence_count=1,
            is_active=True,
        )
        db_session.add(trap)
        db_session.commit()
        loaded = db_session.get(DisqualificationTrap, trap.id)
        assert loaded.trap_code == 'NO_SIGNATURE_PAGE'
        assert loaded.trap_category == 'signature'

    def test_trap_code_unique(self, db_session):
        """DisqualificationTrap trap_code must be unique."""
        from app.models.review import DisqualificationTrap
        trap1 = DisqualificationTrap(
            trap_code='UNIQUE_TRAP',
            trap_category='seal',
            trap_title='First Trap',
            trap_description='First description',
        )
        db_session.add(trap1)
        db_session.commit()
        trap2 = DisqualificationTrap(
            trap_code='UNIQUE_TRAP',
            trap_category='seal',
            trap_title='Second Trap',
            trap_description='Second description',
        )
        db_session.add(trap2)
        with pytest.raises(Exception):
            db_session.commit()

    def test_is_active_defaults_true(self, db_session):
        """is_active defaults to True."""
        from app.models.review import DisqualificationTrap
        trap = DisqualificationTrap(
            trap_code='TEST_TRAP',
            trap_category='price',
            trap_title='Test',
            trap_description='Test desc',
        )
        db_session.add(trap)
        db_session.commit()
        loaded = db_session.get(DisqualificationTrap, trap.id)
        assert loaded.is_active is True

    def test_occurrence_count_defaults_one(self, db_session):
        """occurrence_count defaults to 1."""
        from app.models.review import DisqualificationTrap
        trap = DisqualificationTrap(
            trap_code='OCC_TRAP',
            trap_category='format',
            trap_title='Test',
            trap_description='Test desc',
        )
        db_session.add(trap)
        db_session.commit()
        loaded = db_session.get(DisqualificationTrap, trap.id)
        assert loaded.occurrence_count == 1


class TestDraftRevivalModel:
    def test_create_draft_revival(self, db_session):
        """DraftRevival can be created linked to abandoned_draft and new_project."""
        from app.models.review import DraftRevival
        revival = DraftRevival(
            abandoned_draft_id=1,
            new_project_id=2,
            revival_type='rebid_same_project',
            adaptation_notes='Updated pricing for new bid',
        )
        db_session.add(revival)
        db_session.commit()
        loaded = db_session.get(DraftRevival, revival.id)
        assert loaded.revival_type == 'rebid_same_project'
        assert loaded.new_project_id == 2

    def test_revived_content_json(self, db_session):
        """revived_content stores JSON dict."""
        from app.models.review import DraftRevival
        content = {"sections": ["intro", "pricing"], "modified": ["pricing"]}
        revival = DraftRevival(
            abandoned_draft_id=1,
            new_project_id=2,
            revival_type='similar_project_reference',
            revived_content=content,
        )
        db_session.add(revival)
        db_session.commit()
        loaded = db_session.get(DraftRevival, revival.id)
        assert loaded.revived_content["sections"][0] == "intro"

    def test_is_successful_nullable(self, db_session):
        """is_successful can be NULL (not yet determined)."""
        from app.models.review import DraftRevival
        revival = DraftRevival(
            abandoned_draft_id=1,
            new_project_id=2,
            revival_type='rebid_same_project',
            is_successful=None,
        )
        db_session.add(revival)
        db_session.commit()
        loaded = db_session.get(DraftRevival, revival.id)
        assert loaded.is_successful is None


class TestKnowledgeEvolutionLogModel:
    def test_create_log(self, db_session):
        """KnowledgeEvolutionLog can be created linked to chunk."""
        from app.models.review import KnowledgeEvolutionLog
        log = KnowledgeEvolutionLog(
            chunk_id=1,
            action_type='confirmed_win',
            project_id=1,
            new_quality_score=95,
            reason='Won bid with high score',
        )
        db_session.add(log)
        db_session.commit()
        loaded = db_session.get(KnowledgeEvolutionLog, log.id)
        assert loaded.action_type == 'confirmed_win'
        assert loaded.new_quality_score == 95

    def test_query_by_chunk_id(self, db_session):
        """KnowledgeEvolutionLog can be queried by chunk_id."""
        from app.models.review import KnowledgeEvolutionLog
        log = KnowledgeEvolutionLog(
            chunk_id=1,
            action_type='weighted',
            old_quality_score=80,
            new_quality_score=90,
        )
        db_session.add(log)
        db_session.commit()
        results = db_session.query(KnowledgeEvolutionLog).filter(KnowledgeEvolutionLog.chunk_id == 1).all()
        assert len(results) == 1
