from __future__ import annotations

from sqlalchemy.orm import Session

from app.integrations import text2sql_adapter
from app.models.agent_memory import AgentMemory
from app.repositories import agent_memory_repository


def list_memories(db: Session, agent_id: str) -> list[AgentMemory]:
    return agent_memory_repository.list_by_agent(db, agent_id)


def create_memory(db: Session, agent_id: str, content: str) -> AgentMemory:
    memory = agent_memory_repository.create(db, agent_id=agent_id, content=content)
    db.commit()
    db.refresh(memory)
    # Business rules feed into TextSQL's instructions (see resolve_engine_for_agent in
    # chat_service.py) but aren't covered by knowledge_version, the engine cache's normal
    # invalidation trigger — evict explicitly, same as agent_service.update_agent does for
    # custom_instructions, or a newly-saved rule wouldn't apply until something else evicted
    # the cache.
    text2sql_adapter.invalidate_engine(agent_id)
    return memory


def get_memory_or_none(db: Session, agent_id: str, memory_id: str) -> AgentMemory | None:
    return agent_memory_repository.get_for_agent(db, agent_id, memory_id)


def delete_memory(db: Session, memory: AgentMemory) -> None:
    agent_id = memory.agent_id
    agent_memory_repository.delete(db, memory)
    db.commit()
    text2sql_adapter.invalidate_engine(agent_id)
