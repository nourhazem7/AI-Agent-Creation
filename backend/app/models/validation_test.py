from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import IdTimestampMixin

TEST_ORIGINS = ("ai_generated", "user_created", "uploaded")
RUN_STATUSES = ("not_run", "passed", "failed", "error")


class ValidationTest(IdTimestampMixin, Base):
    __tablename__ = "validation_tests"

    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    origin: Mapped[str] = mapped_column(String(20), default="user_created")

    # True only if expected_sql was actually executed against the connected database and
    # succeeded (checked at creation/import time). False for legacy rows created before this
    # column existed, or when expected_sql is absent/unchecked — never inferred as true.
    expected_sql_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    # Denormalized for cheap listing; ValidationRun rows are the source of truth/history.
    last_status: Mapped[str] = mapped_column(String(20), default="not_run")

    agent: Mapped["Agent"] = relationship(back_populates="validation_tests")
    runs: Mapped[list["ValidationRun"]] = relationship(
        back_populates="test", cascade="all, delete-orphan", order_by="ValidationRun.created_at"
    )
