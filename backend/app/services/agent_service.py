from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.agent import Agent
from app.repositories import agent_repository
from app.schemas.agent import AgentCreate, AgentUpdate


def create_agent(db: Session, *, company_id: str, owner_id: str, payload: AgentCreate) -> Agent:
    agent = agent_repository.create_agent(
        db,
        company_id=company_id,
        owner_id=owner_id,
        name=payload.name,
        description=payload.description,
        llm_model=payload.llm_model or get_settings().llm_model,
        custom_instructions=payload.custom_instructions,
    )
    db.commit()
    db.refresh(agent)
    return agent


def list_agents(db: Session, company_id: str) -> list[Agent]:
    return agent_repository.list_agents_for_company(db, company_id)


def update_agent(db: Session, agent: Agent, payload: AgentUpdate) -> Agent:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)
    db.commit()
    db.refresh(agent)
    return agent


def delete_agent(db: Session, agent: Agent) -> None:
    # From Milestone 6 onward this also evicts the agent's cached TextSQL engine
    # via Text2SQLAdapter.invalidate(agent.id) before the row is deleted.
    agent_repository.delete_agent(db, agent)
    db.commit()
