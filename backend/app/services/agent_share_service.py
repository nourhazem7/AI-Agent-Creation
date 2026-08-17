from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.agent import SHAREABLE_STATUSES, Agent
from app.models.agent_share import SHARE_ROLES, AgentShare
from app.models.user import User
from app.repositories import agent_share_repository, user_repository


def list_shares(db: Session, agent_id: str) -> list[AgentShare]:
    return agent_share_repository.list_by_agent(db, agent_id)


def create_or_update_share(
    db: Session, *, agent: Agent, target_user_id: str, role: str, shared_by: User
) -> AgentShare:
    if role not in SHARE_ROLES:
        raise ValueError(f"role must be one of {SHARE_ROLES}")
    if agent.status not in SHAREABLE_STATUSES:
        raise ValueError("Finish setting up this agent before sharing it.")

    target_user = user_repository.get_user(db, target_user_id)
    if not target_user or target_user.company_id != agent.company_id:
        raise ValueError("User not found in this company.")
    if not target_user.is_active:
        raise ValueError("Cannot share an agent with an inactive user.")
    if target_user.id == agent.owner_id:
        raise ValueError("The agent owner already has full access.")

    existing = agent_share_repository.get_by_agent_and_user(db, agent.id, target_user_id)
    if existing:
        share = agent_share_repository.update_role(db, existing, role)
    else:
        share = agent_share_repository.create(
            db, agent_id=agent.id, user_id=target_user_id, role=role, shared_by_id=shared_by.id
        )

    db.commit()
    db.refresh(share)
    return share


def update_share_role(db: Session, share: AgentShare, role: str) -> AgentShare:
    if role not in SHARE_ROLES:
        raise ValueError(f"role must be one of {SHARE_ROLES}")
    agent_share_repository.update_role(db, share, role)
    db.commit()
    db.refresh(share)
    return share


def revoke_share(db: Session, share: AgentShare) -> None:
    agent_share_repository.delete(db, share)
    db.commit()
