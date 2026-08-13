from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_agent_or_404
from app.models.agent import Agent
from app.models.knowledge_asset import ASSET_TYPES
from app.schemas.knowledge_asset import KnowledgeAssetNotConfigured, KnowledgeAssetOut
from app.services import knowledge_asset_service

router = APIRouter(prefix="/agents/{agent_id}/knowledge-assets", tags=["knowledge-assets"])


def _validate_asset_type(asset_type: str) -> None:
    if asset_type not in ASSET_TYPES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown asset type '{asset_type}'.")


@router.get("", response_model=list[KnowledgeAssetOut | KnowledgeAssetNotConfigured])
def list_assets(
    agent: Agent = Depends(get_agent_or_404),
    db: Session = Depends(get_db),
) -> list:
    existing = {a.asset_type: a for a in knowledge_asset_service.list_assets(db, agent.id)}
    return [existing.get(t) or KnowledgeAssetNotConfigured(asset_type=t) for t in ASSET_TYPES]


@router.get("/{asset_type}", response_model=KnowledgeAssetOut | KnowledgeAssetNotConfigured)
def get_asset(
    asset_type: str,
    agent: Agent = Depends(get_agent_or_404),
    db: Session = Depends(get_db),
):
    _validate_asset_type(asset_type)
    asset = knowledge_asset_service.get_asset(db, agent.id, asset_type)
    return asset or KnowledgeAssetNotConfigured(asset_type=asset_type)


@router.post("/{asset_type}/generate", response_model=KnowledgeAssetOut)
def generate_asset(
    asset_type: str,
    agent: Agent = Depends(get_agent_or_404),
    db: Session = Depends(get_db),
) -> KnowledgeAssetOut:
    _validate_asset_type(asset_type)
    try:
        return knowledge_asset_service.generate_asset(db, agent, asset_type)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.post("/{asset_type}/upload", response_model=KnowledgeAssetOut)
async def upload_asset(
    asset_type: str,
    file: UploadFile,
    agent: Agent = Depends(get_agent_or_404),
    db: Session = Depends(get_db),
) -> KnowledgeAssetOut:
    _validate_asset_type(asset_type)
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No file provided.")
    content = await file.read()
    try:
        return knowledge_asset_service.upload_asset(db, agent, asset_type, file.filename, content)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.delete("/{asset_type}")
def delete_asset(
    asset_type: str,
    agent: Agent = Depends(get_agent_or_404),
    db: Session = Depends(get_db),
) -> dict:
    _validate_asset_type(asset_type)
    knowledge_asset_service.delete_asset(db, agent, asset_type)
    return {"ok": True}
