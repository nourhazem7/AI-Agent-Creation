"""Shared FastAPI dependencies: DB session, current user, agent ownership check."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agent import Agent
from app.models.user import User
from app.repositories.agent_share_repository import get_by_agent_and_user
from app.repositories.user_repository import get_user
from app.security import decode_access_token
from app.services.agent_access import has_min_role, resolve_role

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    user = get_user(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")

    return user


def get_agent_or_404(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Agent:
    """Viewer-or-above access. Agents are private by default: owner, company admins, and
    users with an explicit AgentShare can access; everyone else gets the same 404 as a
    nonexistent agent — existence is never leaked, whether the agent doesn't exist, belongs
    to another company, or simply hasn't been shared with this user.

    On success, the resolved role and (if applicable) share metadata are attached to the
    returned Agent so downstream dependencies/routers can branch on access level without
    re-querying. These are transient attributes, never persisted.
    """
    agent = db.get(Agent, agent_id)
    share = get_by_agent_and_user(db, agent_id, current_user.id) if agent else None
    role = resolve_role(agent, current_user, share) if agent else None

    if not agent or not role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")

    agent.my_role = role
    agent.shared_by = share.shared_by if share else None
    agent.shared_at = share.created_at if share else None
    return agent


def get_agent_editor_or_404(agent: Agent = Depends(get_agent_or_404)) -> Agent:
    """Editor-or-above: owner, company admin, or an editor share."""
    if not has_min_role(agent.my_role, "editor"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have permission to edit this agent")
    return agent


def get_agent_owner_or_404(agent: Agent = Depends(get_agent_or_404)) -> Agent:
    """Owner-or-admin: full control — database connection, sharing, delete."""
    if not has_min_role(agent.my_role, "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have permission to manage this agent")
    return agent
