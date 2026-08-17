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

    status: Mapped[str] = mapped_column(String(20), nullable=False)  # passed | failed | error
    generated_sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list[dict], capped

    # Only populated when the test has a verified expected_sql: the *actual* rows obtained by
    # executing that reference SQL against the real database, at run time. This is the
    # authoritative expected answer — never the natural-language expected_answer description.
    reference_result: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list[dict], capped

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Plain-language explanation of how the verdict was reached — never claim more
    # certainty than a substring/loose comparison actually provides.
    comparison_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    iterations: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    test: Mapped["ValidationTest"] = relationship(back_populates="runs")
