from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.user import UserSummary

# Only "viewer" is a valid share role — see app/models/agent_share.py's SHARE_ROLES.
ShareRole = Literal["viewer"]


class AgentShareCreate(BaseModel):
    user_id: str
    role: ShareRole


class AgentShareUpdate(BaseModel):
    role: ShareRole


class AgentShareOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    role: ShareRole
    user: UserSummary
    shared_by: UserSummary
    created_at: datetime
    updated_at: datetime


class CompanyMemberOut(UserSummary):
    pass
