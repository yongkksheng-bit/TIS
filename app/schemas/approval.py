from pydantic import BaseModel
from typing import Optional


class SpecialistApprovalRequest(BaseModel):
    # Actions:
    #   specialist: 'submit_to_boss' | 'direct_execute' | 'terminate'
    #   boss:        'approve' | 'reject' (from pending_boss_approval or post-specialist states)
    action: str
    generation_mode: str  # 'AUTO' or 'GUIDED'
    user_id: int
    role: Optional[str] = None  # 'specialist' or 'boss'
    override_reason: Optional[str] = None  # required if approving with fatal risks
    # Relationship info (required for boss approval)
    relationship_flag: Optional[bool] = False
    differentiation_guidance: Optional[str] = None

class SpecialistApprovalResponse(BaseModel):
    status: str
    project_status: str

class BossOverrideRequest(BaseModel):
    new_action: str  # 'override_terminate' or 'override_revive'
    new_mode: str  # 'AUTO' or 'GUIDED'
    reason: str  # required
    user_id: int

class BossOverrideResponse(BaseModel):
    status: str
    new_status: str
