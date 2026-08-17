from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrations import text2sql_adapter
from app.models.agent import Agent
from app.models.knowledge_asset import ASSET_TYPES
from app.repositories import agent_repository, database_connection_repository, knowledge_asset_repository
from app.schemas.agent import AgentCreate, AgentOut, AgentUpdate


def _enrich(db: Session, agent: Agent) -> AgentOut:
    """Attach dashboard-card summary fields, always computed fresh from this agent's own
    related rows — never cached, never borrowed from another agent."""
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
    return _enrich(db, agent)


def list_agents(db: Session, company_id: str) -> list[AgentOut]:
    agents = agent_repository.list_agents_for_company(db, company_id)
    return [_enrich(db, agent) for agent in agents]


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
