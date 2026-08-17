from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.repositories.user_repository import list_active_users_for_company
from app.schemas.agent_share import CompanyMemberOut

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/members", response_model=list[CompanyMemberOut])
def list_members(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list:
    return list_active_users_for_company(db, current_user.company_id)
