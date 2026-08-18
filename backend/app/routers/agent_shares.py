from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_agent_owner_or_404, get_current_user
from app.models.agent import Agent
from app.models.user import User
from app.repositories import agent_share_repository
from app.schemas.agent_share import AgentShareCreate, AgentShareOut, AgentShareUpdate
from app.services import agent_share_service

# Every route here requires owner-or-admin (see get_agent_owner_or_404) — a shared
# (viewer) user must never see or manage who else has access, per the sharing spec.
#
# update_share (PATCH) is effectively a no-op now that "viewer" is the only share role —
# kept rather than removed, since deleting an endpoint is a bigger compatibility break than
# leaving one that accepts no other value. Nothing in the frontend calls it anymore.
router = APIRouter(prefix="/agents/{agent_id}/shares", tags=["agent-shares"])


def _get_share_or_404(agent_id: str, share_id: str, db: Session):
    share = agent_share_repository.get_by_id(db, share_id)
    if not share or share.agent_id != agent_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Share not found")
    return share


@router.get("", response_model=list[AgentShareOut])
def list_shares(
    agent: Agent = Depends(get_agent_owner_or_404),
    db: Session = Depends(get_db),
) -> list:
    return agent_share_service.list_shares(db, agent.id)


@router.post("", response_model=AgentShareOut)
def create_share(
    payload: AgentShareCreate,
    agent: Agent = Depends(get_agent_owner_or_404),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return agent_share_service.create_or_update_share(
            db, agent=agent, target_user_id=payload.user_id, role=payload.role, shared_by=current_user
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.patch("/{share_id}", response_model=AgentShareOut)
def update_share(
    share_id: str,
    payload: AgentShareUpdate,
    agent: Agent = Depends(get_agent_owner_or_404),
    db: Session = Depends(get_db),
):
    share = _get_share_or_404(agent.id, share_id, db)
    try:
        return agent_share_service.update_share_role(db, share, payload.role)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.delete("/{share_id}")
def delete_share(
    share_id: str,
    agent: Agent = Depends(get_agent_owner_or_404),
    db: Session = Depends(get_db),
) -> dict:
    share = _get_share_or_404(agent.id, share_id, db)
    agent_share_service.revoke_share(db, share)
    return {"ok": True}
