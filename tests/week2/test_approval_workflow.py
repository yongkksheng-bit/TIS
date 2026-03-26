"""TDD Tests for ApprovalWorkflowService - Option-A Pattern."""
import pytest
import json
from datetime import datetime, timedelta
from sqlalchemy import text

from app.core.week2_evaluation.approval_service import ApprovalWorkflowService
from app.models.enums import ProjectStatus, GenerationMode, ApprovalAction, TimeUrgencyLevel


class TestApprovalWorkflowService:
    """TDD tests for ApprovalWorkflowService following Option-A pattern."""

    @pytest.fixture
    def seed_project_with_report(self, db_session):
        """Create a project with bid_evaluation_report for approval tests."""
        # Create user first
        db_session.execute(text("""
            INSERT INTO users (id, username, email) VALUES (1, 'specialist', 'specialist@test.com')
        """))
        db_session.execute(text("""
            INSERT INTO users (id, username, email) VALUES (2, 'boss', 'boss@test.com')
        """))

        # Create project with bid_open_date = today + 30 days
        bid_date = datetime.now() + timedelta(days=30)
        db_session.execute(text("""
            INSERT INTO projects (id, project_name, project_type, bid_open_date, status, created_by)
            VALUES (1, 'Test Project', 'food', :bid_date, 'evaluation_ready', 1)
        """), {"bid_date": bid_date})

        # Create bid_evaluation_report (no fatal risks, normal time urgency)
        db_session.execute(text("""
            INSERT INTO bid_evaluation_reports (
                id, project_id, report_version, qualification_match_score,
                missing_mandatory_certs, fatal_risks, time_urgency_level,
                recommendation, confirmed_by_specialist
            )
            VALUES (
                1, 1, 1, 85,
                '[]', '[]', 'relaxed',
                'worth_bidding', 0
            )
        """))

        db_session.commit()
        return db_session

    @pytest.fixture
    def seed_project_with_fatal_risks(self, db_session):
        """Create a project with fatal_risks for override reason test."""
        # Create user first
        db_session.execute(text("""
            INSERT INTO users (id, username, email) VALUES (1, 'specialist', 'specialist@test.com')
        """))

        # Create project with bid_open_date = today + 30 days
        bid_date = datetime.now() + timedelta(days=30)
        db_session.execute(text("""
            INSERT INTO projects (id, project_name, project_type, bid_open_date, status, created_by)
            VALUES (1, 'Risky Project', 'food', :bid_date, 'evaluation_ready', 1)
        """), {"bid_date": bid_date})

        # Create bid_evaluation_report with fatal risks
        db_session.execute(text("""
            INSERT INTO bid_evaluation_reports (
                id, project_id, report_version, qualification_match_score,
                missing_mandatory_certs, fatal_risks, time_urgency_level,
                recommendation, confirmed_by_specialist
            )
            VALUES (
                1, 1, 1, 85,
                '[]', '["Missing mandatory certificate: FOOD-BUSINESS-LICENSE"]',
                'relaxed', 'abandon', 0
            )
        """))

        db_session.commit()
        return db_session

    @pytest.fixture
    def seed_project_expired(self, db_session):
        """Create a project with expired time_urgency_level."""
        # Create user first
        db_session.execute(text("""
            INSERT INTO users (id, username, email) VALUES (1, 'specialist', 'specialist@test.com')
        """))

        # Create project with bid_open_date = yesterday (expired)
        bid_date = datetime.now() - timedelta(days=1)
        db_session.execute(text("""
            INSERT INTO projects (id, project_name, project_type, bid_open_date, status, created_by)
            VALUES (1, 'Expired Project', 'food', :bid_date, 'evaluation_ready', 1)
        """), {"bid_date": bid_date})

        # Create bid_evaluation_report with expired time urgency
        db_session.execute(text("""
            INSERT INTO bid_evaluation_reports (
                id, project_id, report_version, qualification_match_score,
                missing_mandatory_certs, fatal_risks, time_urgency_level,
                recommendation, confirmed_by_specialist
            )
            VALUES (
                1, 1, 1, 85,
                '[]', '[]', 'expired', 'abandon', 0
            )
        """))

        db_session.commit()
        return db_session

    def test_specialist_approve_with_mode_lock(self, db_session, seed_project_with_report):
        """Specialist approves with AUTO mode -> verify Project.status=APPROVED_BY_SPECIALIST AND generation_mode=AUTO."""
        service = ApprovalWorkflowService(db_session)
        service.process_specialist_approval(
            report_id=1,
            action='approve',
            generation_mode='AUTO',
            user_id=1
        )

        # Verify project status and generation_mode
        result = db_session.execute(
            text("SELECT status, generation_mode FROM projects WHERE id = 1")
        ).fetchone()

        assert result[0] == 'approved_by_specialist', f"Expected status 'approved_by_specialist', got '{result[0]}'"
        assert result[1] == 'auto', f"Expected generation_mode 'auto', got '{result[1]}'"

    def test_specialist_reject_sets_correct_status(self, db_session, seed_project_with_report):
        """Specialist rejects -> verify Project.status=REJECTED_BY_SPECIALIST, no generation_mode change."""
        service = ApprovalWorkflowService(db_session)
        service.process_specialist_approval(
            report_id=1,
            action='reject',
            generation_mode='GUIDED',  # Should be ignored on reject
            user_id=1
        )

        # Verify project status
        result = db_session.execute(
            text("SELECT status, generation_mode FROM projects WHERE id = 1")
        ).fetchone()

        assert result[0] == 'rejected_by_specialist', f"Expected status 'rejected_by_specialist', got '{result[0]}'"
        assert result[1] is None, f"Expected generation_mode to be None (unchanged), got '{result[1]}'"

    def test_specialist_approve_with_fatal_risks_requires_reason(self, db_session, seed_project_with_fatal_risks):
        """Fatal risks + approve without reason (len<10) -> raises ValueError."""
        service = ApprovalWorkflowService(db_session)

        with pytest.raises(ValueError) as exc_info:
            service.process_specialist_approval(
                report_id=1,
                action='approve',
                generation_mode='AUTO',
                user_id=1,
                override_reason='short'  # Less than 10 chars
            )

        assert "at least 10 characters" in str(exc_info.value).lower() or "override reason" in str(exc_info.value).lower()

        # Verify status was NOT changed
        result = db_session.execute(
            text("SELECT status FROM projects WHERE id = 1")
        ).fetchone()
        assert result[0] == 'evaluation_ready', "Project status should remain unchanged when approval fails"

    def test_specialist_approve_with_fatal_risks_with_valid_reason(self, db_session, seed_project_with_fatal_risks):
        """Fatal risks + approve WITH valid reason (>=10 chars) -> should succeed."""
        service = ApprovalWorkflowService(db_session)
        service.process_specialist_approval(
            report_id=1,
            action='approve',
            generation_mode='AUTO',
            user_id=1,
            override_reason='Acceptable risk - certificate is being processed'
        )

        # Verify project status changed to approved
        result = db_session.execute(
            text("SELECT status FROM projects WHERE id = 1")
        ).fetchone()
        assert result[0] == 'approved_by_specialist'

    def test_specialist_approve_expired_rejected(self, db_session, seed_project_expired):
        """time_urgency_level='expired' + approve -> raises ValueError."""
        service = ApprovalWorkflowService(db_session)

        with pytest.raises(ValueError) as exc_info:
            service.process_specialist_approval(
                report_id=1,
                action='approve',
                generation_mode='AUTO',
                user_id=1
            )

        assert "expired" in str(exc_info.value).lower()

        # Verify status was NOT changed
        result = db_session.execute(
            text("SELECT status FROM projects WHERE id = 1")
        ).fetchone()
        assert result[0] == 'evaluation_ready', "Project status should remain unchanged when approval fails"

    def test_boss_override_terminate_creates_discard_record(self, db_session, seed_project_with_report):
        """Boss terminates -> verify DiscardedProject created AND ApprovalLog entry."""
        # First, specialist approves
        service = ApprovalWorkflowService(db_session)
        service.process_specialist_approval(
            report_id=1,
            action='approve',
            generation_mode='AUTO',
            user_id=1
        )

        # Boss overrides to terminate
        service.process_boss_override(
            report_id=1,
            new_action='override_terminate',
            new_mode='GUIDED',
            reason='Budget constraints - cannot proceed',
            user_id=2
        )

        # Verify project status changed to terminated
        result = db_session.execute(
            text("SELECT status FROM projects WHERE id = 1")
        ).fetchone()
        assert result[0] == 'terminated_by_boss', f"Expected status 'terminated_by_boss', got '{result[0]}'"

        # Verify DiscardedProject was created
        discard_result = db_session.execute(
            text("SELECT project_id, discarded_by, can_be_revived FROM discarded_projects WHERE project_id = 1")
        ).fetchone()
        assert discard_result is not None, "DiscardedProject record should be created"
        assert discard_result[1] == 'boss', f"Expected discarded_by 'boss', got '{discard_result[1]}'"
        assert discard_result[2] == 1, "can_be_revived should be True (1)"

        # Verify ApprovalLog was created for boss override
        log_result = db_session.execute(
            text("SELECT action_type, actor_role FROM approval_logs WHERE project_id = 1 AND action_type = 'boss_override_terminate'")
        ).fetchone()
        assert log_result is not None, "ApprovalLog entry should be created for boss override"

    def test_boss_override_revive_updates_project(self, db_session, seed_project_with_report):
        """Boss revives rejected -> verify Project.status=APPROVED_BY_SPECIALIST AND DiscardedProject.revived_at updated."""
        # First, specialist rejects
        service = ApprovalWorkflowService(db_session)
        service.process_specialist_approval(
            report_id=1,
            action='reject',
            generation_mode='GUIDED',
            user_id=1
        )

        # Boss overrides to revive
        service.process_boss_override(
            report_id=1,
            new_action='override_revive',
            new_mode='AUTO',
            reason='Important project - needs participation',
            user_id=2
        )

        # Verify project status changed back to approved
        result = db_session.execute(
            text("SELECT status FROM projects WHERE id = 1")
        ).fetchone()
        assert result[0] == 'approved_by_specialist', f"Expected status 'approved_by_specialist', got '{result[0]}'"

        # Verify generation_mode was updated to new_mode
        result = db_session.execute(
            text("SELECT generation_mode FROM projects WHERE id = 1")
        ).fetchone()
        assert result[0] == 'auto', f"Expected generation_mode 'auto' (from boss override), got '{result[0]}'"

        # Verify DiscardedProject was revived (revived_at set)
        discard_result = db_session.execute(
            text("SELECT revived_at, revived_by FROM discarded_projects WHERE project_id = 1")
        ).fetchone()
        assert discard_result is not None, "DiscardedProject record should exist"
        assert discard_result[0] is not None, "revived_at should be set"
        assert discard_result[1] == 2, f"Expected revived_by user_id 2, got '{discard_result[1]}'"

    def test_audit_log_created_for_specialist(self, db_session, seed_project_with_report):
        """Verify ApprovalLog row exists after specialist decision."""
        service = ApprovalWorkflowService(db_session)
        service.process_specialist_approval(
            report_id=1,
            action='approve',
            generation_mode='AUTO',
            user_id=1
        )

        # Verify ApprovalLog was created
        log_result = db_session.execute(
            text("""
                SELECT project_id, action_type, actor_role, actor_id, original_status, new_status
                FROM approval_logs
                WHERE project_id = 1
            """)
        ).fetchone()

        assert log_result is not None, "ApprovalLog entry should be created"
        assert log_result[0] == 1, "project_id should be 1"
        assert log_result[1] == 'specialist_worthy', f"Expected action_type 'specialist_worthy', got '{log_result[1]}'"
        assert log_result[2] == 'specialist', f"Expected actor_role 'specialist', got '{log_result[2]}'"
        assert log_result[3] == 1, f"Expected actor_id 1, got '{log_result[3]}'"
        assert log_result[4] == 'evaluation_ready', f"Expected original_status 'evaluation_ready', got '{log_result[4]}'"
        assert log_result[5] == 'approved_by_specialist', f"Expected new_status 'approved_by_specialist', got '{log_result[5]}'"

    def test_audit_log_created_for_boss_override(self, db_session, seed_project_with_report):
        """Verify ApprovalLog row exists after boss override."""
        # First, specialist approves
        service = ApprovalWorkflowService(db_session)
        service.process_specialist_approval(
            report_id=1,
            action='approve',
            generation_mode='AUTO',
            user_id=1
        )

        # Boss overrides to terminate
        service.process_boss_override(
            report_id=1,
            new_action='override_terminate',
            new_mode='GUIDED',
            reason='Budget constraints',
            user_id=2
        )

        # Verify ApprovalLog for boss override
        log_result = db_session.execute(
            text("""
                SELECT action_type, actor_role, actor_id, reason_text, original_status, new_status
                FROM approval_logs
                WHERE project_id = 1 AND action_type = 'boss_override_terminate'
            """)
        ).fetchone()

        assert log_result is not None, "ApprovalLog entry should be created for boss override"
        assert log_result[0] == 'boss_override_terminate', f"Expected action_type 'boss_override_terminate', got '{log_result[0]}'"
        assert log_result[1] == 'boss', f"Expected actor_role 'boss', got '{log_result[1]}'"
        assert log_result[2] == 2, f"Expected actor_id 2, got '{log_result[2]}'"
        assert log_result[3] == 'Budget constraints', f"Expected reason_text 'Budget constraints', got '{log_result[3]}'"
        assert log_result[4] == 'approved_by_specialist', f"Expected original_status 'approved_by_specialist', got '{log_result[4]}'"
        assert log_result[5] == 'terminated_by_boss', f"Expected new_status 'terminated_by_boss', got '{log_result[5]}'"

    def test_specialist_approve_guided_mode_sets_correct_mode(self, db_session, seed_project_with_report):
        """Specialist approves with GUIDED mode -> verify generation_mode=guided."""
        service = ApprovalWorkflowService(db_session)
        service.process_specialist_approval(
            report_id=1,
            action='approve',
            generation_mode='GUIDED',
            user_id=1
        )

        result = db_session.execute(
            text("SELECT generation_mode FROM projects WHERE id = 1")
        ).fetchone()

        assert result[0] == 'guided', f"Expected generation_mode 'guided', got '{result[0]}'"

    def test_report_overridden_by_boss_flag_set(self, db_session, seed_project_with_report):
        """Verify BidEvaluationReport.overridden_by_boss=True and boss_override_reason set after override."""
        # First, specialist approves
        service = ApprovalWorkflowService(db_session)
        service.process_specialist_approval(
            report_id=1,
            action='approve',
            generation_mode='AUTO',
            user_id=1
        )

        # Boss overrides
        service.process_boss_override(
            report_id=1,
            new_action='override_terminate',
            new_mode='GUIDED',
            reason='Final budget cut',
            user_id=2
        )

        # Verify report flags
        result = db_session.execute(
            text("SELECT overridden_by_boss, boss_override_reason FROM bid_evaluation_reports WHERE project_id = 1")
        ).fetchone()

        assert result[0] == 1, f"Expected overridden_by_boss=True (1), got '{result[0]}'"
        assert result[1] == 'Final budget cut', f"Expected boss_override_reason 'Final budget cut', got '{result[1]}'"
