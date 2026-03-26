"""TDD Tests for BidEvaluationEngine - Week 2 Orchestrator."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from app.core.week2_evaluation.evaluation_engine import BidEvaluationEngine
from app.models.enums import Recommendation, RiskLevel, RelationshipLevel, TimeUrgencyLevel


class TestBidEvaluationEngine:
    """TDD tests for BidEvaluationEngine orchestration."""

    @pytest.fixture
    def seed_project(self, db_session):
        """Create a project with all necessary data for evaluation."""
        from sqlalchemy import text
        import json

        # Create user first
        db_session.execute(text("""
            INSERT INTO users (id, username, email) VALUES (1, 'testuser', 'test@test.com')
        """))

        # Create project with bid_open_date = today + 30 days
        bid_date = datetime.now() + timedelta(days=30)
        db_session.execute(text("""
            INSERT INTO projects (id, project_name, project_type, owner_unit, region, bid_open_date, status, created_by)
            VALUES (1, 'Test Project', 'food', '某市政府', '杭州', :bid_date, 'uploaded', 1)
        """), {"bid_date": bid_date})

        # Create tender document with qualification requirements
        tender_data = json.dumps({
            'qualification_requirements': [
                {'cert_code': 'FOOD-BUSINESS-LICENSE', 'is_mandatory': True},
                {'cert_code': 'ISO-9001-2015', 'is_mandatory': False},
            ]
        })
        db_session.execute(text("""
            INSERT INTO tender_documents (project_id, parsing_status, extracted_data, parsed_by_ai, confirmed_by_human)
            VALUES (1, 'completed', :data, 1, 1)
        """), {"data": tender_data})

        # Create bid document and image for OCR extractions
        db_session.execute(text("""
            INSERT INTO bid_documents (id, project_id, doc_type) VALUES (1, 1, 'qualification')
        """))
        db_session.execute(text("""
            INSERT INTO document_images (id, document_id, project_id, image_type, ocr_status)
            VALUES (1, 1, 1, 'certification', 'success')
        """))

        db_session.commit()
        return db_session

    @pytest.fixture
    def seed_certs(self, seed_project):
        """Seed standard certifications for week 2 tests."""
        from sqlalchemy import text
        import json

        session = seed_project
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

    def test_generate_report_returns_all_sections(self, db_session, seed_certs, seed_project):
        """Verify all expected keys are present in the generated report dict."""
        # Mock all sub-components to isolate the engine test
        with patch('app.core.week2_evaluation.evaluation_engine.QualificationMatcher') as MockQual, \
             patch('app.core.week2_evaluation.evaluation_engine.TimeEvaluator') as MockTime, \
             patch('app.core.week2_evaluation.evaluation_engine.OwnerProfileService') as MockOwner, \
             patch('app.core.week2_evaluation.evaluation_engine.CostEstimator') as MockCost, \
             patch('app.core.week2_evaluation.evaluation_engine.WinProbabilityCalculator') as MockWin:

            # Configure mocks
            MockQual.return_value.exact_match_evaluation.return_value = {
                'qualification_match_score': 100,
                'is_qualification_pass': True,
                'missing_mandatory_certs': [],
                'missing_optional_certs': [],
                'matched_certs': [{'cert_code': 'FOOD-BUSINESS-LICENSE'}]
            }
            MockTime.return_value.calculate.return_value = {
                'days_until_bid_open': 30,
                'time_urgency_level': 'relaxed',
                'is_time_sufficient': True
            }
            MockOwner.return_value.get_profile.return_value = MagicMock(
                id=1,
                owner_name='某市政府',
                region='杭州',
                relationship_level=RelationshipLevel.STRONG,
                cooperation_count=5,
                preferred_styles={'style': '高效务实'},
                is_new_owner=False
            )
            MockCost.return_value.estimate.return_value = MagicMock(
                estimated_cost=100000.0,
                cost_range_low=90000.0,
                cost_range_high=115000.0,
                confidence='medium'
            )
            MockWin.return_value.calculate.return_value = 0.75

            engine = BidEvaluationEngine(db_session, project_id=1)
            report = engine.generate_report()

            # Verify all expected top-level keys
            expected_keys = [
                'report_id', 'qualification', 'time', 'owner', 'cost',
                'probability', 'recommendation', 'risks'
            ]
            for key in expected_keys:
                assert key in report, f"Missing expected key: {key}"

            # Verify qualification section
            assert 'qualification_match_score' in report['qualification']
            assert 'is_qualification_pass' in report['qualification']
            assert 'missing_mandatory_certs' in report['qualification']
            assert 'missing_optional_certs' in report['qualification']
            assert 'matched_certs' in report['qualification']

            # Verify time section
            assert 'days_until_bid_open' in report['time']
            assert 'time_urgency_level' in report['time']
            assert 'is_time_sufficient' in report['time']

            # Verify owner section
            assert 'owner_profile_id' in report['owner']
            assert 'relationship_index' in report['owner']
            assert 'is_new_owner' in report['owner']

            # Verify cost section
            assert 'estimated_cost' in report['cost']
            assert 'suggested_price_range_low' in report['cost']
            assert 'suggested_price_range_high' in report['cost']
            assert 'cost_estimate_confidence' in report['cost']

            # Verify probability section
            assert 'overall_win_probability' in report['probability']

            # Verify recommendation section
            assert 'recommendation' in report['recommendation']
            assert 'recommendation_reason' in report['recommendation']

            # Verify risks section
            assert 'fatal_risks' in report['risks']
            assert 'warning_risks' in report['risks']
            assert 'risk_level' in report['risks']

    def test_expired_bid_gives_abandon_recommendation(self, db_session, seed_certs, seed_project):
        """When time_evaluator returns 'expired', recommendation should be 'abandon'."""
        with patch('app.core.week2_evaluation.evaluation_engine.QualificationMatcher') as MockQual, \
             patch('app.core.week2_evaluation.evaluation_engine.TimeEvaluator') as MockTime, \
             patch('app.core.week2_evaluation.evaluation_engine.OwnerProfileService') as MockOwner, \
             patch('app.core.week2_evaluation.evaluation_engine.CostEstimator') as MockCost, \
             patch('app.core.week2_evaluation.evaluation_engine.WinProbabilityCalculator') as MockWin:

            MockQual.return_value.exact_match_evaluation.return_value = {
                'qualification_match_score': 100,
                'is_qualification_pass': True,
                'missing_mandatory_certs': [],
                'missing_optional_certs': [],
                'matched_certs': []
            }
            # Simulate expired bid
            MockTime.return_value.calculate.return_value = {
                'days_until_bid_open': -5,
                'time_urgency_level': 'expired',
                'is_time_sufficient': False
            }
            MockOwner.return_value.get_profile.return_value = MagicMock(
                id=None, is_new_owner=True, relationship_level=RelationshipLevel.NONE.value
            )
            MockCost.return_value.estimate.return_value = MagicMock(
                estimated_cost=100000.0, cost_range_low=90000.0,
                cost_range_high=115000.0, confidence='low'
            )
            MockWin.return_value.calculate.return_value = 0.0

            engine = BidEvaluationEngine(db_session, project_id=1)
            report = engine.generate_report()

            assert report['recommendation']['recommendation'] == 'abandon'
            assert 'expired' in str(report['risks']['fatal_risks']).lower()

    def test_fatal_qual_score_gives_abandon(self, db_session, seed_certs, seed_project):
        """When qualification score < 60, recommendation should be 'abandon'."""
        with patch('app.core.week2_evaluation.evaluation_engine.QualificationMatcher') as MockQual, \
             patch('app.core.week2_evaluation.evaluation_engine.TimeEvaluator') as MockTime, \
             patch('app.core.week2_evaluation.evaluation_engine.OwnerProfileService') as MockOwner, \
             patch('app.core.week2_evaluation.evaluation_engine.CostEstimator') as MockCost, \
             patch('app.core.week2_evaluation.evaluation_engine.WinProbabilityCalculator') as MockWin:

            # Score < 60 is fatal
            MockQual.return_value.exact_match_evaluation.return_value = {
                'qualification_match_score': 50,
                'is_qualification_pass': False,
                'missing_mandatory_certs': [{'cert_code': 'FOOD-BUSINESS-LICENSE', 'reason': 'missing'}],
                'missing_optional_certs': [],
                'matched_certs': []
            }
            MockTime.return_value.calculate.return_value = {
                'days_until_bid_open': 30,
                'time_urgency_level': 'relaxed',
                'is_time_sufficient': True
            }
            MockOwner.return_value.get_profile.return_value = MagicMock(
                id=None, is_new_owner=True, relationship_level=RelationshipLevel.NONE.value
            )
            MockCost.return_value.estimate.return_value = MagicMock(
                estimated_cost=100000.0, cost_range_low=90000.0,
                cost_range_high=115000.0, confidence='low'
            )
            MockWin.return_value.calculate.return_value = 0.0

            engine = BidEvaluationEngine(db_session, project_id=1)
            report = engine.generate_report()

            assert report['recommendation']['recommendation'] == 'abandon'

    def test_high_prob_gives_worthy(self, db_session, seed_certs, seed_project):
        """When win_probability > 0.60, recommendation should be 'worth_bidding'."""
        with patch('app.core.week2_evaluation.evaluation_engine.QualificationMatcher') as MockQual, \
             patch('app.core.week2_evaluation.evaluation_engine.TimeEvaluator') as MockTime, \
             patch('app.core.week2_evaluation.evaluation_engine.OwnerProfileService') as MockOwner, \
             patch('app.core.week2_evaluation.evaluation_engine.CostEstimator') as MockCost, \
             patch('app.core.week2_evaluation.evaluation_engine.WinProbabilityCalculator') as MockWin:

            MockQual.return_value.exact_match_evaluation.return_value = {
                'qualification_match_score': 100,
                'is_qualification_pass': True,
                'missing_mandatory_certs': [],
                'missing_optional_certs': [],
                'matched_certs': [{'cert_code': 'FOOD-BUSINESS-LICENSE'}]
            }
            MockTime.return_value.calculate.return_value = {
                'days_until_bid_open': 30,
                'time_urgency_level': 'relaxed',
                'is_time_sufficient': True
            }
            MockOwner.return_value.get_profile.return_value = MagicMock(
                id=1, is_new_owner=False, relationship_level=RelationshipLevel.STRONG.value
            )
            MockCost.return_value.estimate.return_value = MagicMock(
                estimated_cost=100000.0, cost_range_low=90000.0,
                cost_range_high=115000.0, confidence='high'
            )
            MockWin.return_value.calculate.return_value = 0.75

            engine = BidEvaluationEngine(db_session, project_id=1)
            report = engine.generate_report()

            assert report['recommendation']['recommendation'] == 'worth_bidding'

    def test_medium_prob_gives_discuss(self, db_session, seed_certs, seed_project):
        """When 0 < win_probability <= 0.60, recommendation should be 'conditional' (discuss)."""
        with patch('app.core.week2_evaluation.evaluation_engine.QualificationMatcher') as MockQual, \
             patch('app.core.week2_evaluation.evaluation_engine.TimeEvaluator') as MockTime, \
             patch('app.core.week2_evaluation.evaluation_engine.OwnerProfileService') as MockOwner, \
             patch('app.core.week2_evaluation.evaluation_engine.CostEstimator') as MockCost, \
             patch('app.core.week2_evaluation.evaluation_engine.WinProbabilityCalculator') as MockWin:

            MockQual.return_value.exact_match_evaluation.return_value = {
                'qualification_match_score': 80,
                'is_qualification_pass': True,
                'missing_mandatory_certs': [],
                'missing_optional_certs': [],
                'matched_certs': [{'cert_code': 'FOOD-BUSINESS-LICENSE'}]
            }
            MockTime.return_value.calculate.return_value = {
                'days_until_bid_open': 10,
                'time_urgency_level': 'normal',
                'is_time_sufficient': True
            }
            MockOwner.return_value.get_profile.return_value = MagicMock(
                id=1, is_new_owner=False, relationship_level=RelationshipLevel.MEDIUM.value
            )
            MockCost.return_value.estimate.return_value = MagicMock(
                estimated_cost=100000.0, cost_range_low=90000.0,
                cost_range_high=115000.0, confidence='medium'
            )
            MockWin.return_value.calculate.return_value = 0.5

            engine = BidEvaluationEngine(db_session, project_id=1)
            report = engine.generate_report()

            assert report['recommendation']['recommendation'] == 'conditional'

    def test_new_owner_adds_warning_risk(self, db_session, seed_certs, seed_project):
        """When is_new_owner=True, warning_risks should contain a warning."""
        with patch('app.core.week2_evaluation.evaluation_engine.QualificationMatcher') as MockQual, \
             patch('app.core.week2_evaluation.evaluation_engine.TimeEvaluator') as MockTime, \
             patch('app.core.week2_evaluation.evaluation_engine.OwnerProfileService') as MockOwner, \
             patch('app.core.week2_evaluation.evaluation_engine.CostEstimator') as MockCost, \
             patch('app.core.week2_evaluation.evaluation_engine.WinProbabilityCalculator') as MockWin:

            MockQual.return_value.exact_match_evaluation.return_value = {
                'qualification_match_score': 100,
                'is_qualification_pass': True,
                'missing_mandatory_certs': [],
                'missing_optional_certs': [],
                'matched_certs': [{'cert_code': 'FOOD-BUSINESS-LICENSE'}]
            }
            MockTime.return_value.calculate.return_value = {
                'days_until_bid_open': 30,
                'time_urgency_level': 'relaxed',
                'is_time_sufficient': True
            }
            # New owner
            MockOwner.return_value.get_profile.return_value = MagicMock(
                id=None, is_new_owner=True, relationship_level=RelationshipLevel.NONE.value
            )
            MockCost.return_value.estimate.return_value = MagicMock(
                estimated_cost=100000.0, cost_range_low=90000.0,
                cost_range_high=115000.0, confidence='medium'
            )
            MockWin.return_value.calculate.return_value = 0.65

            engine = BidEvaluationEngine(db_session, project_id=1)
            report = engine.generate_report()

            assert len(report['risks']['warning_risks']) > 0
            assert any('new_owner' in str(w).lower() for w in report['risks']['warning_risks'])

    def test_report_persisted_to_db(self, db_session, seed_certs, seed_project):
        """Verify BidEvaluationReport row is created in DB after generate_report()."""
        with patch('app.core.week2_evaluation.evaluation_engine.QualificationMatcher') as MockQual, \
             patch('app.core.week2_evaluation.evaluation_engine.TimeEvaluator') as MockTime, \
             patch('app.core.week2_evaluation.evaluation_engine.OwnerProfileService') as MockOwner, \
             patch('app.core.week2_evaluation.evaluation_engine.CostEstimator') as MockCost, \
             patch('app.core.week2_evaluation.evaluation_engine.WinProbabilityCalculator') as MockWin:

            MockQual.return_value.exact_match_evaluation.return_value = {
                'qualification_match_score': 100,
                'is_qualification_pass': True,
                'missing_mandatory_certs': [],
                'missing_optional_certs': [],
                'matched_certs': [{'cert_code': 'FOOD-BUSINESS-LICENSE'}]
            }
            MockTime.return_value.calculate.return_value = {
                'days_until_bid_open': 30,
                'time_urgency_level': 'relaxed',
                'is_time_sufficient': True
            }
            MockOwner.return_value.get_profile.return_value = MagicMock(
                id=1, is_new_owner=False, relationship_level=RelationshipLevel.STRONG.value
            )
            MockCost.return_value.estimate.return_value = MagicMock(
                estimated_cost=100000.0, cost_range_low=90000.0,
                cost_range_high=115000.0, confidence='medium'
            )
            MockWin.return_value.calculate.return_value = 0.75

            engine = BidEvaluationEngine(db_session, project_id=1)
            report = engine.generate_report()

            # Query DB for the report
            from sqlalchemy import text
            result = db_session.execute(
                text("SELECT * FROM bid_evaluation_reports WHERE project_id = 1")
            ).fetchone()

            assert result is not None, "BidEvaluationReport was not persisted to DB"
            assert result[1] == 1, "report_version should be 1"  # project_id is index 1
