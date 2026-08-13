from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import IdTimestampMixin

# Lifecycle: draft -> connecting -> configuring_knowledge -> preparing
#            -> ready_for_validation -> validated -> active   (or -> error at any step)
AGENT_STATUSES = (
    "draft",
    "connecting",
    "configuring_knowledge",
    "preparing",
    "ready_for_validation",
    "validated",
    "active",
    "error",
)


class Agent(IdTimestampMixin, Base):
    __tablename__ = "agents"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft")

    # No hardcoded provider default here — agent_service.create_agent() resolves this
    # from Settings.llm_model (the company-configured model) when not explicitly given,
    # so the default lives in one place (config), not duplicated across model/schema/UI.
    llm_model: Mapped[str] = mapped_column(String(100))
    # Future business-rules seam: passed straight through to TextSQL(instructions=...).
    custom_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Bumped whenever the DB connection or a knowledge asset changes.
    # The Text2SQLAdapter uses (agent_id, knowledge_version) as its engine cache key.
    knowledge_version: Mapped[int] = mapped_column(Integer, default=0)

    company: Mapped["Company"] = relationship(back_populates="agents")
    owner: Mapped["User"] = relationship(back_populates="agents_owned")

    database_connection: Mapped["DatabaseConnection | None"] = relationship(
        back_populates="agent", cascade="all, delete-orphan", uselist=False
    )
    knowledge_assets: Mapped[list["KnowledgeAsset"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )
    validation_tests: Mapped[list["ValidationTest"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )
