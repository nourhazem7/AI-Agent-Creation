from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import new_uuid, utcnow

# Only "text" and "table" are ever produced in v1. The field exists now so future
# structured outputs (kpi/chart) don't require a migration.
RESPONSE_TYPES = ("text", "table", "kpi", "chart")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id"), nullable=False, index=True
    )

    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant
    # The primary displayed text. For an assistant reply this is the business-language
    # normalized answer (see text2sql_adapter.normalize_business_answer) — never the agent's
    # raw markdown-laden commentary directly.
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # The agent's original, unnormalized commentary — preserved for debugging/API inspection.
    # Null for user messages and for any assistant message that predates this column (legacy
    # rows: content itself was the only text that ever existed for them, nothing was lost).
    raw_answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list[dict], capped
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_type: Mapped[str] = mapped_column(String(20), default="text")

    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
