from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_agent_or_404, get_current_user
from app.models.agent import Agent
from app.models.user import User
from app.schemas.agent import AgentCreate, AgentOut, AgentUpdate
from app.services import agent_service

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentOut])
def list_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Agent]:
    return agent_service.list_agents(db, current_user.company_id)


@router.post("", response_model=AgentOut)
def create_agent(
    payload: AgentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Agent:
    return agent_service.create_agent(
        db, company_id=current_user.company_id, owner_id=current_user.id, payload=payload
    )


@router.get("/{agent_id}", response_model=AgentOut)
def get_agent(agent: Agent = Depends(get_agent_or_404)) -> Agent:
    return agent


@router.patch("/{agent_id}", response_model=AgentOut)
def update_agent(
    payload: AgentUpdate,
    agent: Agent = Depends(get_agent_or_404),
    db: Session = Depends(get_db),
) -> Agent:
    return agent_service.update_agent(db, agent, payload)


@router.delete("/{agent_id}")
def delete_agent(agent: Agent = Depends(get_agent_or_404), db: Session = Depends(get_db)) -> dict:
    agent_service.delete_agent(db, agent)
    return {"ok": True}
