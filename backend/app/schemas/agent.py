from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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
    name: str
    description: str | None
    status: str
    llm_model: str
    custom_instructions: str | None
    knowledge_version: int
    created_at: datetime
    updated_at: datetime
