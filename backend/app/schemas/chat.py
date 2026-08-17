from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    role: str
    content: str
    sql: str | None
    result_data: str | None
    error_message: str | None
    response_type: str
    input_tokens: int | None
    output_tokens: int | None
    created_at: datetime


class MessageCreateRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
