from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import new_uuid, utcnow


class ValidationRun(Base):
    """One execution of a ValidationTest. History is kept — rows are never overwritten."""

    __tablename__ = "validation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    validation_test_id: Mapped[str] = mapped_column(
        ForeignKey("validation_tests.id"), nullable=False, index=True
    )
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False)  # see RUN_STATUSES
    generated_sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list[dict], capped

    # The agent's own natural-language commentary for this run — "what Agent One actually
    # determined," shown as the primary answer in the UI (the raw table is supporting detail).
    agent_answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Only populated when the test has a verified expected_sql: the rows obtained by executing
    # that reference solution against the real database, at run time. This is "what the
    # reference solution returned" — one possible answer, NOT the authoritative correct answer.
    # The verdict is never derived from comparing this to result_data (see validation_service).
    reference_result: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list[dict], capped

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The judge's reasoning for its verdict (or, for technical errors, a plain explanation of
    # what went wrong before the judge was ever consulted).
    comparison_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Short, specific phrase naming the requirement the judge found missing/violated — e.g.
    # "missing Bank Transfer total" — populated only for partial/failed verdicts.
    violated_requirement: Mapped[str | None] = mapped_column(Text, nullable=True)

    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    iterations: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    test: Mapped["ValidationTest"] = relationship(back_populates="runs")
