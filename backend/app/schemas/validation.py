from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ValidationRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    generated_sql: str | None
    result_data: str | None
    reference_result: str | None
    error_message: str | None
    comparison_note: str | None
    input_tokens: int | None
    output_tokens: int | None
    iterations: int | None
    created_at: datetime


class ValidationTestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    question: str
    expected_sql: str | None
    expected_answer: str | None
    notes: str | None
    origin: str
    expected_sql_verified: bool
    last_status: str
    created_at: datetime
    updated_at: datetime
    latest_run: ValidationRunOut | None = None


class ValidationTestCreate(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    expected_sql: str | None = Field(default=None, max_length=8000)
    expected_answer: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)


class RunSummary(BaseModel):
    total: int
    passed: int
    failed: int
    error: int
    not_run: int
