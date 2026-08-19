from __future__ import annotations

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import IdTimestampMixin


class AgentMemory(IdTimestampMixin, Base):
    """A single, manually-added persistent business rule/definition for one Agent — e.g.
    "Revenue excludes cancelled orders." Deliberately minimal for v1: no categories, tags,
    priorities, confidence, or per-user scoping. See app/integrations/text2sql_adapter.py's
    combine_instructions() for how these reach SQL generation."""

    __tablename__ = "agent_memories"

    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    agent: Mapped["Agent"] = relationship(back_populates="memories")
