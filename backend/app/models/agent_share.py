from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import IdTimestampMixin

# Only "viewer" is creatable — sharing grants use/read access only, never modify rights.
# A pre-existing row with role="editor" (from before this change) may still exist in an
# already-deployed database; agent_access.resolve_role() normalizes any stored role to the
# same "viewer" access level rather than trusting the column, so no data migration is
# needed and no legacy row can ever grant elevated access.
SHARE_ROLES = ("viewer",)


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
