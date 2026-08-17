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
    # True only if THIS asset actually passed the current grounding/verification pipeline.
    # False for legacy assets generated before that pipeline existed — never inferred from
    # source/status alone, so a pre-upgrade "ready" asset never falsely claims verification.
    verified: bool = False
    created_at: datetime
    updated_at: datetime


class KnowledgeAssetNotConfigured(BaseModel):
    asset_type: str
    source: None = None
    status: str = "not_configured"
    verified: bool = False
