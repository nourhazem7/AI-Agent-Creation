from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation


def create(db: Session, *, agent_id: str, user_id: str, title: str = "New chat") -> Conversation:
    conversation = Conversation(agent_id=agent_id, user_id=user_id, title=title)
    db.add(conversation)
    db.flush()
    return conversation


def get(db: Session, conversation_id: str) -> Conversation | None:
    return db.get(Conversation, conversation_id)


def list_by_agent(db: Session, agent_id: str) -> list[Conversation]:
    stmt = (
        select(Conversation)
        .where(Conversation.agent_id == agent_id)
        .order_by(Conversation.updated_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def delete(db: Session, conversation: Conversation) -> None:
    db.delete(conversation)
