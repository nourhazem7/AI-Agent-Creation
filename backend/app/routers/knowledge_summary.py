from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_agent_or_404
from app.models.agent import Agent
from app.schemas.knowledge_summary import KnowledgeSummaryOut
from app.services import knowledge_summary_service

router = APIRouter(prefix="/agents/{agent_id}/knowledge-summary", tags=["knowledge-summary"])


@router.get("", response_model=KnowledgeSummaryOut)
def get_knowledge_summary(
    agent: Agent = Depends(get_agent_or_404),
    db: Session = Depends(get_db),
) -> KnowledgeSummaryOut:
    return knowledge_summary_service.get_summary(db, agent)
