from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class UserSummary(BaseModel):
    """Minimal, safe-to-share user info — used wherever another user's identity needs to be
    shown (share grants, "shared by") without exposing role/company/timestamps."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str | None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    email: str
    full_name: str | None
    role: str
    created_at: datetime


class MeResponse(BaseModel):
    user: UserOut
    company: CompanyOut
