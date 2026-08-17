from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import IdTimestampMixin

SHARE_ROLES = ("viewer", "editor")


class AgentShare(IdTimestampMixin, Base):
    __tablename__ = "agent_shares"
    __table_args__ = (UniqueConstraint("agent_id", "user_id", name="uq_agent_share_user"),)

    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    shared_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)

    agent: Mapped["Agent"] = relationship(back_populates="shares")
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    shared_by: Mapped["User"] = relationship(foreign_keys=[shared_by_id])
