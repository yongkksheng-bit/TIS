"""DraftRevivalEngine — revives abandoned drafts for rebidding."""
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.models.formal_review import AbandonedDraft
from app.models.review import DraftRevival
from app.models.project import Project


class DraftRevivalEngine:
    """
    Revives abandoned drafts for rebidding on the same project.

    Called when a boss decides to rebid on a project that was previously
    terminated during formal review or pricing stages.
    """

    def __init__(self, db: Session, draft_id: int):
        self.db = db
        self.draft_id = draft_id

    def revive_draft(self, user_id: int, reason: str) -> dict:
        """
        Revive an abandoned draft for rebidding.

        Args:
            user_id: ID of the user triggering the revival
            reason: Adaptation/revival reason

        Returns:
            dict with keys: revival_id, revived_content, message

        Raises:
            ValueError: If draft not found, not revivable, or expired (>12 months)
        """
        # Step 1: Load draft
        draft = (
            self.db.query(AbandonedDraft)
            .filter(AbandonedDraft.id == self.draft_id)
            .first()
        )

        # Step 2: Defensive check — draft not found
        if draft is None:
            raise ValueError("Abandoned draft not found")

        # Step 3: Defensive check — can_be_revived must be True
        if not draft.can_be_revived:
            raise ValueError("Draft is marked as non-revivable")

        # Step 4: Check 12-month expiry
        if draft.archived_at is None:
            raise ValueError("Draft has no archived_at timestamp")

        now = datetime.now(timezone.utc)
        # Handle naive datetime by attaching UTC
        archived_at = draft.archived_at
        if archived_at.tzinfo is None:
            archived_at = archived_at.replace(tzinfo=timezone.utc)

        expiry_threshold = archived_at + timedelta(days=365)
        if now > expiry_threshold:
            raise ValueError("Draft revival period (12 months) has expired")

        # Step 5: Update AbandonedDraft
        original_project_id = draft.project_id
        draft.revived_at = now
        draft.revived_to_project_id = original_project_id
        draft.can_be_revived = False

        # Step 6: Restore project status to evaluation_ready
        project = self.db.get(Project, original_project_id)
        if project is None:
            raise ValueError("Associated project not found")
        project.status = "evaluation_ready"

        # Step 7: Record in draft_revivals table
        revived_content = {
            "original_project_id": original_project_id,
            "termination_reason": draft.termination_reason,
            "revival_type": "rebid_same_project",
        }

        draft_revival = DraftRevival(
            abandoned_draft_id=self.draft_id,
            new_project_id=original_project_id,
            revival_type="rebid_same_project",
            revived_content=revived_content,
            adaptation_notes=reason,
            revived_by=user_id,
            revived_at=now,
            is_successful=True,
        )
        self.db.add(draft_revival)
        self.db.commit()

        # Step 8: Return result
        return {
            "revival_id": draft_revival.id,
            "revived_content": revived_content,
            "message": f"Draft {self.draft_id} revived successfully for rebid on project {original_project_id}",
        }
