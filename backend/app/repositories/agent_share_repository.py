from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_share import AgentShare


def get_by_agent_and_user(db: Session, agent_id: str, user_id: str) -> AgentShare | None:
    stmt = select(AgentShare).where(AgentShare.agent_id == agent_id, AgentShare.user_id == user_id)
    return db.execute(stmt).scalar_one_or_none()


def get_by_id(db: Session, share_id: str) -> AgentShare | None:
    return db.get(AgentShare, share_id)


def list_by_agent(db: Session, agent_id: str) -> list[AgentShare]:
    stmt = (
        select(AgentShare)
        .where(AgentShare.agent_id == agent_id)
        .order_by(AgentShare.created_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


def list_by_user(db: Session, user_id: str) -> list[AgentShare]:
    """All shares granted to this user, across every agent — used to attach access
    metadata in bulk when listing agents, instead of one query per agent."""
    stmt = select(AgentShare).where(AgentShare.user_id == user_id)
    return list(db.execute(stmt).scalars().all())


def create(db: Session, *, agent_id: str, user_id: str, role: str, shared_by_id: str) -> AgentShare:
    share = AgentShare(agent_id=agent_id, user_id=user_id, role=role, shared_by_id=shared_by_id)
    db.add(share)
    db.flush()
    return share


def update_role(db: Session, share: AgentShare, role: str) -> AgentShare:
    share.role = role
    db.flush()
    return share


def delete(db: Session, share: AgentShare) -> None:
    db.delete(share)
