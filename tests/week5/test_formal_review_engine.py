"""Tests for FormalReviewEngine."""
import pytest
from unittest.mock import MagicMock
from datetime import date, datetime

from app.core.week5_formal_review.formal_review_engine import (
    FormalReviewEngine,
    archive_project_to_abandoned_drafts,
)


class TestFormalReviewEngine:
    """Test suite for FormalReviewEngine."""

    def test_generate_checklist_returns_list(self):
        """Returns a list of checklist items."""
        db = MagicMock()
        project_id = 1

        # Mock project
        project = MagicMock()
        project.id = 1
        project.bid_open_date = date(2026, 4, 15)
        db.get.return_value = project

        # Mock qualifications query - empty
        db.query.return_value.filter.return_value.all.return_value = []

        # Mock pricing decision query - empty
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        # Mock tech proposal query - empty
        db.query.return_value.filter.return_value.first.return_value = None

        engine = FormalReviewEngine(db, project_id)
        result = engine.generate_review_checklist()

        assert isinstance(result, list)

    def test_qualification_validity_fatal_when_expired(self):
        """valid_until < bid_open_date → fatal item."""
        db = MagicMock()
        project_id = 1

        # Mock project with bid_open_date = 2026-04-15
        project = MagicMock()
        project.id = 1
        project.bid_open_date = date(2026, 4, 15)
        db.get.return_value = project

        # Mock qualification with valid_until = 2026-03-01 (expired)
        qualification = MagicMock()
        qualification.id = 10
        qualification.standard_cert_id = 5
        qualification.normalized_value = "ISO22000"
        qualification.valid_until = date(2026, 3, 1)  # expired before bid_open_date

        # Mock tender document
        tender = MagicMock()
        tender.extracted_scoring_std = None
        tender.extracted_seal_requirements = None
        db.query.return_value.filter.return_value.first.return_value = tender

        # Mock qualifications query
        db.query.return_value.filter.return_value.all.return_value = [qualification]

        # Mock pricing decision query - empty
        def pricing_query_side_effect(*args):
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.first.return_value = None
            return mock_query

        # Set up different return values for different query calls
        call_count = [0]
        def query_side_effect(*args):
            call_count[0] += 1
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            if call_count[0] == 1:  # First query = OCR extractions
                mock_q.all.return_value = [qualification]
            elif call_count[0] == 2:  # Second query = pricing decision
                mock_q.first.return_value = None
            elif call_count[0] == 3:  # Third query = tech proposal
                mock_q.first.return_value = None
            else:
                mock_q.first.return_value = None
            return mock_q

        db.query.side_effect = query_side_effect

        engine = FormalReviewEngine(db, project_id)
        result = engine.generate_review_checklist()

        # Assert one item with risk_level='fatal' in returned checklist
        fatal_items = [item for item in result if item.get('risk_level') == 'fatal']
        assert len(fatal_items) >= 1
        fatal_item = fatal_items[0]
        assert fatal_item['check_category'] == 'qualification_validity'
        assert 'ISO22000' in fatal_item['check_title']

    def test_qualification_validity_warning_when_expiring_soon(self):
        """valid_until within 90 days of bid_open_date → warning item."""
        db = MagicMock()
        project_id = 1

        # Mock project with bid_open_date = 2026-04-15
        project = MagicMock()
        project.id = 1
        project.bid_open_date = date(2026, 4, 15)
        db.get.return_value = project

        # Mock qualification with valid_until = 2026-06-01 (within 90 days of bid_open_date)
        qualification = MagicMock()
        qualification.id = 10
        qualification.standard_cert_id = 5
        qualification.normalized_value = "ISO9001"
        qualification.valid_until = date(2026, 6, 1)  # within 90 days of 2026-04-15

        # Mock tender document
        tender = MagicMock()
        tender.extracted_scoring_std = None
        tender.extracted_seal_requirements = None
        db.query.return_value.filter.return_value.first.return_value = tender

        # Set up query mock
        call_count = [0]
        def query_side_effect(*args):
            call_count[0] += 1
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            if call_count[0] == 1:
                mock_q.all.return_value = [qualification]
            else:
                mock_q.first.return_value = None
            return mock_q

        db.query.side_effect = query_side_effect

        engine = FormalReviewEngine(db, project_id)
        result = engine.generate_review_checklist()

        warning_items = [item for item in result if item.get('risk_level') == 'warning']
        assert len(warning_items) >= 1
        warning_item = warning_items[0]
        assert warning_item['check_category'] == 'qualification_validity'
        assert warning_item['system_status'] == 'warning'

    def test_price_over_budget_limit_generates_fatal(self):
        """boss_final_price > budget_limit → fatal price_compliance item."""
        db = MagicMock()
        project_id = 1

        # Mock project
        project = MagicMock()
        project.id = 1
        project.bid_open_date = date(2026, 4, 15)
        db.get.return_value = project

        # Mock pricing decision with boss_final_price > budget_limit
        pricing_decision = MagicMock()
        pricing_decision.id = 100
        pricing_decision.boss_final_price = 150.0
        pricing_decision.budget_limit = 100.0
        pricing_decision.status = 'decided'

        # Mock tender document
        tender = MagicMock()
        tender.extracted_scoring_std = None
        tender.extracted_seal_requirements = None
        db.query.return_value.filter.return_value.first.return_value = tender

        # Set up query mock
        call_count = [0]
        def query_side_effect(*args):
            call_count[0] += 1
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            if call_count[0] == 1:
                mock_q.all.return_value = []
            elif call_count[0] == 2:
                mock_q.first.return_value = pricing_decision
            else:
                mock_q.first.return_value = None
            return mock_q

        db.query.side_effect = query_side_effect

        engine = FormalReviewEngine(db, project_id)
        result = engine.generate_review_checklist()

        fatal_items = [item for item in result if item.get('risk_level') == 'fatal']
        price_items = [item for item in fatal_items if item.get('check_category') == 'price_compliance']
        assert len(price_items) >= 1

    def test_price_within_budget_generates_pass(self):
        """boss_final_price <= budget_limit → passed/info item."""
        db = MagicMock()
        project_id = 1

        # Mock project
        project = MagicMock()
        project.id = 1
        project.bid_open_date = date(2026, 4, 15)
        db.get.return_value = project

        # Mock pricing decision with boss_final_price <= budget_limit
        pricing_decision = MagicMock()
        pricing_decision.id = 100
        pricing_decision.boss_final_price = 80.0
        pricing_decision.budget_limit = 100.0
        pricing_decision.status = 'decided'

        # Mock tender document
        tender = MagicMock()
        tender.extracted_scoring_std = None
        tender.extracted_seal_requirements = None
        db.query.return_value.filter.return_value.first.return_value = tender

        # Set up query mock
        call_count = [0]
        def query_side_effect(*args):
            call_count[0] += 1
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            if call_count[0] == 1:
                mock_q.all.return_value = []
            elif call_count[0] == 2:
                mock_q.first.return_value = pricing_decision
            else:
                mock_q.first.return_value = None
            return mock_q

        db.query.side_effect = query_side_effect

        engine = FormalReviewEngine(db, project_id)
        result = engine.generate_review_checklist()

        passed_items = [item for item in result if item.get('system_status') == 'passed']
        price_items = [item for item in passed_items if item.get('check_category') == 'price_compliance']
        assert len(price_items) >= 1

    def test_archive_project_creates_abandoned_draft(self):
        """archive_project_to_abandoned_drafts() creates a record."""
        db = MagicMock()
        project_id = 1
        termination_stage = 'formal_review'
        termination_reason = 'Boss decided to abandon'
        user_id = 42

        # Mock pricing decision
        pricing_decision = MagicMock()
        pricing_decision.id = 100

        def query_side_effect(*args):
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            mock_q.first.return_value = pricing_decision
            return mock_q

        db.query.side_effect = query_side_effect

        archive_project_to_abandoned_drafts(
            db, project_id, termination_stage, termination_reason, user_id
        )

        # Assert db.add and db.commit called
        assert db.add.called
        assert db.commit.called


class TestArchiveProject:
    """Test archive_project_to_abandoned_drafts function."""

    def test_archive_project_sets_can_be_revived_true(self):
        """Abandoned draft should have can_be_revived=True."""
        db = MagicMock()
        project_id = 1
        termination_stage = 'formal_review'
        termination_reason = 'Test reason'
        user_id = 42

        def query_side_effect(*args):
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            mock_q.first.return_value = None
            return mock_q

        db.query.side_effect = query_side_effect

        archive_project_to_abandoned_drafts(
            db, project_id, termination_stage, termination_reason, user_id
        )

        # Get the argument passed to db.add
        call_args = db.add.call_args
        added_object = call_args[0][0]

        assert added_object.can_be_revived is True
        assert added_object.project_id == project_id
        assert added_object.termination_stage == termination_stage
        assert added_object.termination_reason == termination_reason
        assert added_object.termination_by == user_id
