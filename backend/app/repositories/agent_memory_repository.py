from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_memory import AgentMemory


def list_by_agent(db: Session, agent_id: str) -> list[AgentMemory]:
    stmt = (
        select(AgentMemory)
        .where(AgentMemory.agent_id == agent_id)
        .order_by(AgentMemory.created_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


def get_for_agent(db: Session, agent_id: str, memory_id: str) -> AgentMemory | None:
    stmt = select(AgentMemory).where(AgentMemory.agent_id == agent_id, AgentMemory.id == memory_id)
    return db.execute(stmt).scalar_one_or_none()


def create(db: Session, *, agent_id: str, content: str) -> AgentMemory:
    memory = AgentMemory(agent_id=agent_id, content=content)
    db.add(memory)
    db.flush()
    return memory


def delete(db: Session, memory: AgentMemory) -> None:
    db.delete(memory)
