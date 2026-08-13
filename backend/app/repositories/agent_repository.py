from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent


def create_agent(
    db: Session,
    *,
    company_id: str,
    owner_id: str,
    name: str,
    description: str | None,
    llm_model: str,
    custom_instructions: str | None,
) -> Agent:
    agent = Agent(
        company_id=company_id,
        owner_id=owner_id,
        name=name,
        description=description,
        llm_model=llm_model,
        custom_instructions=custom_instructions,
        status="draft",
    )
    db.add(agent)
    db.flush()
    return agent


def list_agents_for_company(db: Session, company_id: str) -> list[Agent]:
    stmt = select(Agent).where(Agent.company_id == company_id).order_by(Agent.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def delete_agent(db: Session, agent: Agent) -> None:
    db.delete(agent)
