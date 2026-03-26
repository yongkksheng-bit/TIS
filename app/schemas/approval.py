from pydantic import BaseModel
from typing import Optional

class SpecialistApprovalRequest(BaseModel):
    action: str  # 'approve' or 'reject'
    generation_mode: str  # 'AUTO' or 'GUIDED' (required per Option-A spec)
    user_id: int
    override_reason: Optional[str] = None  # required if approving with fatal risks

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
