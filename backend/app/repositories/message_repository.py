from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.message import Message


def create(
    db: Session,
    *,
    conversation_id: str,
    role: str,
    content: str,
    sql: str | None = None,
    result_data: str | None = None,
    error_message: str | None = None,
    response_type: str = "text",
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        sql=sql,
        result_data=result_data,
        error_message=error_message,
        response_type=response_type,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    db.add(message)
    db.flush()
    return message


def list_by_conversation(db: Session, conversation_id: str) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return list(db.execute(stmt).scalars().all())
