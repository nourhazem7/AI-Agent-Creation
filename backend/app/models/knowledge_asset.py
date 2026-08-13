from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
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

    agent: Mapped["Agent"] = relationship(back_populates="knowledge_assets")
