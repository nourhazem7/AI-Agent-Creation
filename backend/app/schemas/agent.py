from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserSummary

AgentAccessRole = Literal["owner", "admin", "editor", "viewer"]


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    # Optional — omit to use the company-configured model (Settings.llm_model).
    # Not something the UI needs to ask the user to choose.
    llm_model: str | None = None
    custom_instructions: str | None = None


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    llm_model: str | None = None
    custom_instructions: str | None = None


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    owner_id: str
    owner: UserSummary
    name: str
    description: str | None
    status: str
    llm_model: str
    custom_instructions: str | None
    knowledge_version: int
    created_at: datetime
    updated_at: datetime

    # Access metadata — computed per-request by app/services/agent_access.py, never stored.
    # my_role is always present; shared_by/shared_at are set only when access comes from an
    # explicit AgentShare (my_role in {"editor", "viewer"}) — never for owner/admin access,
    # so the frontend can't mistake an admin's implicit reach for "shared with me".
    my_role: AgentAccessRole
    shared_by: UserSummary | None = None
    shared_at: datetime | None = None
