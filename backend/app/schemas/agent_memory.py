from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_MAX_CONTENT_LENGTH = 2000


class AgentMemoryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=_MAX_CONTENT_LENGTH)

    @field_validator("content")
    @classmethod
    def _trim_and_require_nonempty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("content cannot be empty")
        return trimmed


class AgentMemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    content: str
    created_at: datetime
    updated_at: datetime
