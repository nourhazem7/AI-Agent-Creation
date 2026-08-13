from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KnowledgeAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    asset_type: str
    source: str | None
    status: str
    content: str | None
    original_filename: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class KnowledgeAssetNotConfigured(BaseModel):
    asset_type: str
    source: None = None
    status: str = "not_configured"
