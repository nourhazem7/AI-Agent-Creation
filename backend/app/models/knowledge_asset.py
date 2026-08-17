from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import IdTimestampMixin

ASSET_TYPES = ("schema", "documentation", "validation_suite")
ASSET_SOURCES = ("generated", "uploaded")
ASSET_STATUSES = ("not_configured", "generating", "ready", "error")


class KnowledgeAsset(IdTimestampMixin, Base):
    __tablename__ = "knowledge_assets"
    __table_args__ = (UniqueConstraint("agent_id", "asset_type", name="uq_agent_asset_type"),)

    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="not_configured")

    # schema: JSON dump of Database.get_schema_summary(); documentation: markdown;
    # validation_suite: JSON list of staged {question, expected_sql?, expected_answer?} dicts.
    content: Mapped[str | None] = mapped_column(Text, nullable=True)

    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # True only when this exact asset actually passed the current grounding/verification
    # pipeline (schema: re-diffed against live metadata; documentation: backtick references
    # checked against the schema). Added after assets already existed in production, so it
    # defaults to False via a server-side default on the ALTER TABLE migration (see
    # database.py's _ensure_knowledge_asset_columns) — legacy rows correctly show as
    # "not verified by the current pipeline" rather than falsely claiming verification they
    # never actually underwent. Never backfilled/regenerated automatically.
    verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    agent: Mapped["Agent"] = relationship(back_populates="knowledge_assets")
