from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrations import text2sql_adapter
from app.models.agent import Agent
from app.models.knowledge_asset import ASSET_TYPES
from app.models.user import User
from app.repositories import (
    agent_repository,
    agent_share_repository,
    database_connection_repository,
    knowledge_asset_repository,
)
from app.schemas.agent import AgentCreate, AgentOut, AgentUpdate
from app.services.agent_access import resolve_role


def _enrich(db: Session, agent: Agent) -> AgentOut:
    """Attach dashboard-card summary fields, always computed fresh from this agent's own
    related rows — never cached, never borrowed from another agent."""
    if not hasattr(agent, "my_role"):
        # my_role/shared_by/shared_at are transient attributes normally set by the
        # get_agent_or_404 dependency chain (or by create_agent/list_agents below) before
        # this runs. A caller that fetches its own Agent instance and calls a service
        # function directly — as tests and scripts legitimately do — never goes through
        # that chain, so default to "owner" here rather than raising. Real HTTP responses
        # always have this set explicitly; this default only helps out-of-request callers.
        agent.my_role = "owner"
        agent.shared_by = None
        agent.shared_at = None
    out = AgentOut.model_validate(agent)

    conn = database_connection_repository.get_by_agent(db, agent.id)
    out.database_connected = bool(conn and conn.is_connected)

    assets = knowledge_asset_repository.list_by_agent(db, agent.id)
    out.knowledge_ready_count = sum(1 for a in assets if a.status == "ready")
    out.knowledge_total_count = len(ASSET_TYPES)

    return out


def create_agent(db: Session, *, company_id: str, owner_id: str, payload: AgentCreate) -> AgentOut:
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
    return _enrich(db, agent)


def list_agents(db: Session, current_user: User) -> list[AgentOut]:
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
        visible.append(_enrich(db, agent))

    return visible


def get_agent_detail(db: Session, agent: Agent) -> AgentOut:
    return _enrich(db, agent)


def update_agent(db: Session, agent: Agent, payload: AgentUpdate) -> AgentOut:
    for field, value in payload.model_dump(exclude_unset=True).items():
        # llm_model is NOT NULL — an explicit null means "use the company default",
        # not "clear the column" (which would otherwise 500 on the DB constraint).
        if field == "llm_model" and not value:
            value = get_settings().llm_model
        setattr(agent, field, value)
    db.commit()
    db.refresh(agent)

    # llm_model/custom_instructions feed directly into TextSQL construction but don't bump
    # knowledge_version (that's reserved for DB-connection/knowledge-asset changes) — so the
    # cached engine must be evicted explicitly here, or chat would keep answering with the
    # agent's old model/instructions after an update. Renaming (name/description) doesn't
    # need this, but invalidating unconditionally is cheap and always safe.
    text2sql_adapter.invalidate_engine(agent.id)
    return _enrich(db, agent)


def delete_agent(db: Session, agent: Agent) -> None:
    text2sql_adapter.invalidate_engine(agent.id)
    agent_repository.delete_agent(db, agent)
    db.commit()
