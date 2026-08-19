from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_agent_or_404, get_agent_owner_or_404
from app.models.agent import Agent
from app.schemas.agent_memory import AgentMemoryCreate, AgentMemoryOut
from app.services import agent_memory_service

router = APIRouter(prefix="/agents/{agent_id}/memory", tags=["agent-memory"])


@router.get("", response_model=list[AgentMemoryOut])
def list_memory(agent: Agent = Depends(get_agent_or_404), db: Session = Depends(get_db)) -> list:
    return agent_memory_service.list_memories(db, agent.id)


@router.post("", response_model=AgentMemoryOut)
def create_memory(
    payload: AgentMemoryCreate,
    agent: Agent = Depends(get_agent_owner_or_404),
    db: Session = Depends(get_db),
) -> AgentMemoryOut:
    return agent_memory_service.create_memory(db, agent.id, payload.content)


@router.delete("/{memory_id}")
def delete_memory(
    memory_id: str,
    agent: Agent = Depends(get_agent_owner_or_404),
    db: Session = Depends(get_db),
) -> dict:
    memory = agent_memory_service.get_memory_or_none(db, agent.id, memory_id)
    if not memory:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business rule not found")
    agent_memory_service.delete_memory(db, memory)
    return {"ok": True}
