"""Shared FastAPI dependencies: DB session, current user, agent ownership check."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agent import Agent
from app.models.user import User
from app.repositories.user_repository import get_user
from app.security import decode_access_token

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
    agent = db.get(Agent, agent_id)
    if not agent or agent.company_id != current_user.company_id:
        # Same 404 whether the agent doesn't exist or belongs to another company —
        # don't leak which agent IDs exist.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    return agent
