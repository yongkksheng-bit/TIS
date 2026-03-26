"""Mode Switch Service - handles generation_mode transitions per Master Spec §5.3."""
from sqlalchemy.orm import Session
from app.models.project import Project
from app.models.tech_proposal import TechProposalTask


class ModeSwitchService:
    """
    Handles generation_mode switches with mandatory rollback procedures.

    AUTO → GUIDED (升维):
      - Mark current proposal as 'archived_due_to_mode_switch'
      - Require specialist to re-enter insider notes
      - Start fresh generation

    GUIDED → AUTO (降维):
      - Mark current proposal as 'discarded_due_to_mode_switch'
      - Resume full AUTO RAG pipeline
    """

    def switch_mode(
        self,
        db: Session,
        project_id: int,
        new_mode: str,
        operator_id: int
    ) -> dict:
        """Switch project from current generation_mode to new_mode."""
        project = db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        old_mode = project.generation_mode

        if old_mode == new_mode:
            return {'status': 'unchanged', 'old_mode': old_mode}

        # Find the most recent task for this project
        task = (
            db.query(TechProposalTask)
            .filter_by(project_id=project_id)
            .order_by(TechProposalTask.created_at.desc())
            .first()
        )

        if task:
            if old_mode == 'auto' and new_mode == 'guided':
                task.status = 'archived_due_to_mode_switch'
            elif old_mode == 'guided' and new_mode == 'auto':
                task.status = 'discarded_due_to_mode_switch'

        project.generation_mode = new_mode
        db.commit()

        return {'status': 'switched', 'old_mode': old_mode, 'new_mode': new_mode}