from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.agent import Agent
from app.models.user import User
from app.repositories import agent_repository, agent_share_repository
from app.schemas.agent import AgentCreate, AgentUpdate
from app.services.agent_access import resolve_role


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

    # The creator is always the owner — set directly rather than routing through
    # get_agent_or_404, since this agent didn't exist until the line above.
    agent.my_role = "owner"
    agent.shared_by = None
    agent.shared_at = None
    return agent


def list_agents(db: Session, current_user: User) -> list[Agent]:
    is_admin = current_user.role == "admin"
    agents = agent_repository.list_visible_agents(
        db, company_id=current_user.company_id, user_id=current_user.id, is_admin=is_admin
    )

    # One query for all of this user's shares, instead of one per agent.
    shares_by_agent_id = {
        s.agent_id: s for s in agent_share_repository.list_by_user(db, current_user.id)
    }

    visible = []
    for agent in agents:
        share = shares_by_agent_id.get(agent.id)
        role = resolve_role(agent, current_user, share)
        if role is None:
            # Belt-and-suspenders: the repository query already excludes shares on
            # non-shareable agents, but never surface an agent this user has no role on.
            continue
        agent.my_role = role
        # Only an explicit share counts as "shared with me" — owner/admin access never sets these.
        agent.shared_by = share.shared_by if share else None
        agent.shared_at = share.created_at if share else None
        visible.append(agent)

    return visible


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
