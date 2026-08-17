from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_agent_editor_or_404, get_agent_or_404
from app.models.agent import Agent
from app.models.knowledge_asset import ASSET_TYPES
from app.schemas.knowledge_asset import KnowledgeAssetNotConfigured, KnowledgeAssetOut
from app.services import knowledge_asset_service

router = APIRouter(prefix="/agents/{agent_id}/knowledge-assets", tags=["knowledge-assets"])


def _validate_asset_type(asset_type: str) -> None:
    if asset_type not in ASSET_TYPES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown asset type '{asset_type}'.")


def _to_out(asset, asset_type: str) -> KnowledgeAssetOut | KnowledgeAssetNotConfigured:
    return KnowledgeAssetOut.model_validate(asset) if asset else KnowledgeAssetNotConfigured(asset_type=asset_type)


def _redact_if_viewer(
    item: KnowledgeAssetOut | KnowledgeAssetNotConfigured, my_role: str
) -> KnowledgeAssetOut | KnowledgeAssetNotConfigured:
    # error_message can echo raw DB-driver exception text (built from the real, decrypted
    # connection string) — safe for editor/owner/admin to see and fix, not for viewer.
    if my_role != "viewer" or isinstance(item, KnowledgeAssetNotConfigured):
        return item
    return item.model_copy(update={"error_message": None})


@router.get("", response_model=list[KnowledgeAssetOut | KnowledgeAssetNotConfigured])
def list_assets(
    agent: Agent = Depends(get_agent_or_404),
    db: Session = Depends(get_db),
) -> list:
    existing = {a.asset_type: a for a in knowledge_asset_service.list_assets(db, agent.id)}
    return [
        _redact_if_viewer(_to_out(existing.get(t), t), agent.my_role) for t in ASSET_TYPES
    ]


@router.get("/{asset_type}", response_model=KnowledgeAssetOut | KnowledgeAssetNotConfigured)
def get_asset(
    asset_type: str,
    agent: Agent = Depends(get_agent_or_404),
    db: Session = Depends(get_db),
):
    _validate_asset_type(asset_type)
    asset = knowledge_asset_service.get_asset(db, agent.id, asset_type)
    return _redact_if_viewer(_to_out(asset, asset_type), agent.my_role)


@router.post("/{asset_type}/generate", response_model=KnowledgeAssetOut)
def generate_asset(
    asset_type: str,
    agent: Agent = Depends(get_agent_editor_or_404),
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
    agent: Agent = Depends(get_agent_editor_or_404),
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
    agent: Agent = Depends(get_agent_editor_or_404),
    db: Session = Depends(get_db),
) -> dict:
    _validate_asset_type(asset_type)
    knowledge_asset_service.delete_asset(db, agent, asset_type)
    return {"ok": True}
