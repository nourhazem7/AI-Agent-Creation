from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.agent import SHAREABLE_STATUSES, Agent
from app.models.agent_share import AgentShare


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


def list_visible_agents(db: Session, *, company_id: str, user_id: str, is_admin: bool) -> list[Agent]:
    """Agents private-by-default is enforced here: an ordinary user only ever gets agents
    they own or were explicitly shared with. Admins get full company visibility, never
    agents from another company."""
    if is_admin:
        stmt = select(Agent).where(Agent.company_id == company_id)
    else:
        # A share only counts while the agent is actually shareable — see
        # app/services/agent_access.py's resolve_role, which enforces the same rule for
        # direct access. Filtered here too so a stale/draft share never costs a fetched row.
        shared_agent_ids = select(AgentShare.agent_id).where(AgentShare.user_id == user_id)
        stmt = select(Agent).where(
            Agent.company_id == company_id,
            or_(
                Agent.owner_id == user_id,
                Agent.id.in_(shared_agent_ids) & Agent.status.in_(SHAREABLE_STATUSES),
            ),
        )
    stmt = stmt.order_by(Agent.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def delete_agent(db: Session, agent: Agent) -> None:
    db.delete(agent)
