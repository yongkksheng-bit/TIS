"""ApprovalWorkflowService - Option-A Pattern Implementation.

This service implements the Option-A approval pattern from Master Spec §6 R2:
- Specialist has independent approval authority (worthy/unworthy), takes effect immediately
- Boss has post-hoc oversight (can override with reason, recorded in audit log)
- All operations logged in approval_logs table (immutable audit trail)
"""
from datetime import datetime
from typing import Optional
import json

from sqlalchemy.orm import Session
from sqlalchemy import select, update

from app.models.enums import (
    ProjectStatus,
    GenerationMode,
    ApprovalAction,
    TimeUrgencyLevel,
)
from app.models.evaluation import BidEvaluationReport
from app.models.project import Project
from app.models.approval import ApprovalLog
from app.models.discarded import DiscardedProject


class ApprovalWorkflowService:
    """Service for handling specialist approvals and boss overrides."""

    def __init__(self, db_session: Session):
        """Initialize the service with a database session.

        Args:
            db_session: SQLAlchemy database session
        """
        self.db_session = db_session

    def process_specialist_approval(
        self,
        report_id: int,
        action: str,
        generation_mode: str,
        user_id: int,
        override_reason: Optional[str] = None,
    ) -> None:
        """Process specialist approval decision.

        Args:
            report_id: ID of the BidEvaluationReport
            action: 'approve' or 'reject'
            generation_mode: 'AUTO' or 'GUIDED' (the mode the specialist selects)
            user_id: ID of the specialist user
            override_reason: Required when approving a project with fatal_risks (min 10 chars)

        Raises:
            ValueError: If action is 'approve' with fatal_risks but no valid override_reason,
                       or if action is 'approve' on an expired project
        """
        # Get the bid evaluation report using ORM
        report = self.db_session.get(BidEvaluationReport, report_id)

        if not report:
            raise ValueError(f"BidEvaluationReport with id {report_id} not found")

        # Get the project
        project = self.db_session.get(Project, report.project_id)

        if not project:
            raise ValueError(f"Project with id {report.project_id} not found")

        original_status = project.status.value if hasattr(project.status, 'value') else project.status

        # Check for expired time urgency - REJECT with error
        time_urgency = report.time_urgency_level.value if hasattr(report.time_urgency_level, 'value') else report.time_urgency_level
        if action == 'approve' and time_urgency == TimeUrgencyLevel.EXPIRED.value:
            raise ValueError(
                f"Cannot approve project with time_urgency_level='expired'. "
                f"Project {report.project_id} has expired bid deadline."
            )

        # Check for fatal risks requiring override reason
        # Handle both list (from PostgreSQL JSON) and JSON string (from SQLite TEXT)
        fatal_risks_raw = report.fatal_risks
        if fatal_risks_raw is None:
            fatal_risks_list = []
        elif isinstance(fatal_risks_raw, list):
            fatal_risks_list = fatal_risks_raw
        elif isinstance(fatal_risks_raw, str):
            try:
                fatal_risks_list = json.loads(fatal_risks_raw)
            except json.JSONDecodeError:
                fatal_risks_list = []
        else:
            fatal_risks_list = []

        if action == 'approve' and len(fatal_risks_list) > 0:
            if not override_reason or len(override_reason) < 10:
                raise ValueError(
                    f"Approval of project with fatal_risks requires override_reason "
                    f"with at least 10 characters. Got: {override_reason}"
                )

        # Determine new status based on action
        if action == 'approve':
            new_status = ProjectStatus.APPROVED_BY_SPECIALIST
            new_generation_mode = GenerationMode.AUTO if generation_mode == 'AUTO' else GenerationMode.GUIDED
        elif action == 'reject':
            new_status = ProjectStatus.REJECTED_BY_SPECIALIST
            new_generation_mode = None  # Don't change generation_mode on reject
        else:
            raise ValueError(f"Invalid action: {action}. Must be 'approve' or 'reject'.")

        # Update project status and generation_mode if approving
        project.status = new_status
        if new_generation_mode:
            project.generation_mode = new_generation_mode

        # Update bid_evaluation_report
        report.confirmed_by_specialist = True
        report.specialist_decision = action
        report.confirmed_at = datetime.now()

        # Create audit log entry
        action_type = (
            ApprovalAction.SPECIALIST_WORTHY
            if action == 'approve'
            else ApprovalAction.SPECIALIST_UNWORTHY
        )

        audit_log = ApprovalLog(
            project_id=project.id,
            action_type=action_type,
            actor_role='specialist',
            actor_id=user_id,
            reason_text=override_reason,
            original_status=original_status,
            new_status=new_status.value,
        )
        self.db_session.add(audit_log)

        self.db_session.commit()

    def process_boss_override(
        self,
        report_id: int,
        new_action: str,
        new_mode: str,
        reason: str,
        user_id: int,
    ) -> None:
        """Process boss override decision.

        Args:
            report_id: ID of the BidEvaluationReport
            new_action: 'override_terminate' or 'override_revive'
            new_mode: new generation_mode (can change from what specialist set)
            reason: reason for the override
            user_id: ID of the boss user

        Raises:
            ValueError: If new_action is invalid or project is not in correct status
        """
        # Get the bid evaluation report using ORM
        report = self.db_session.get(BidEvaluationReport, report_id)

        if not report:
            raise ValueError(f"BidEvaluationReport with id {report_id} not found")

        # Get the project
        project = self.db_session.get(Project, report.project_id)

        if not project:
            raise ValueError(f"Project with id {report.project_id} not found")

        current_status = project.status.value if hasattr(project.status, 'value') else project.status

        # Validate new_action
        if new_action not in ('override_terminate', 'override_revive'):
            raise ValueError(
                f"Invalid new_action: {new_action}. "
                f"Must be 'override_terminate' or 'override_revive'."
            )

        # Process based on new_action
        if new_action == 'override_terminate':
            # Only from APPROVED_BY_SPECIALIST -> TERMINATED_BY_BOSS
            if current_status != ProjectStatus.APPROVED_BY_SPECIALIST.value:
                raise ValueError(
                    f"Cannot terminate project in status '{current_status}'. "
                    f"Must be in 'approved_by_specialist' status."
                )

            new_status = ProjectStatus.TERMINATED_BY_BOSS

            # Update project status
            project.status = new_status

            # Create DiscardedProject record
            discarded = DiscardedProject(
                project_id=project.id,
                original_evaluation_report_id=report_id,
                discarded_by='boss',
                discard_reason=reason,
                discard_stage='specialist_approved',
                can_be_revived=True,
            )
            self.db_session.add(discarded)

            action_type = ApprovalAction.BOSS_OVERRIDE_TERMINATE

        elif new_action == 'override_revive':
            # Only from REJECTED_BY_SPECIALIST -> APPROVED_BY_SPECIALIST
            if current_status != ProjectStatus.REJECTED_BY_SPECIALIST.value:
                raise ValueError(
                    f"Cannot revive project in status '{current_status}'. "
                    f"Must be in 'rejected_by_specialist' status."
                )

            new_status = ProjectStatus.APPROVED_BY_SPECIALIST
            new_generation_mode = GenerationMode.AUTO if new_mode == 'AUTO' else GenerationMode.GUIDED

            # Update project status and generation_mode
            project.status = new_status
            project.generation_mode = new_generation_mode

            # Mark the DiscardedProject as revived (if exists)
            discarded = self.db_session.execute(
                select(DiscardedProject).where(DiscardedProject.project_id == project.id)
            ).scalar_one_or_none()

            if discarded:
                discarded.revived_at = datetime.now()
                discarded.revived_by = user_id
            else:
                # If no discarded record exists, create one with revived info
                discarded = DiscardedProject(
                    project_id=project.id,
                    original_evaluation_report_id=report_id,
                    discarded_by='specialist',
                    discard_reason='Initial rejection',
                    discard_stage='specialist_rejected',
                    can_be_revived=True,
                    revived_at=datetime.now(),
                    revived_by=user_id,
                )
                self.db_session.add(discarded)

            action_type = ApprovalAction.BOSS_OVERRIDE_REVIVE

        # Update bid_evaluation_report with boss override info
        report.overridden_by_boss = True
        report.boss_override_reason = reason

        # Create audit log entry
        audit_log = ApprovalLog(
            project_id=project.id,
            action_type=action_type,
            actor_role='boss',
            actor_id=user_id,
            reason_text=reason,
            original_status=current_status,
            new_status=new_status.value,
        )
        self.db_session.add(audit_log)

        self.db_session.commit()
