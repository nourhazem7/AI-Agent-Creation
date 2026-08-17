from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge_asset import KnowledgeAsset


def get_by_agent_and_type(db: Session, agent_id: str, asset_type: str) -> KnowledgeAsset | None:
    stmt = select(KnowledgeAsset).where(
        KnowledgeAsset.agent_id == agent_id, KnowledgeAsset.asset_type == asset_type
    )
    return db.execute(stmt).scalar_one_or_none()


def list_by_agent(db: Session, agent_id: str) -> list[KnowledgeAsset]:
    stmt = select(KnowledgeAsset).where(KnowledgeAsset.agent_id == agent_id)
    return list(db.execute(stmt).scalars().all())


def upsert(
    db: Session,
    *,
    agent_id: str,
    asset_type: str,
    source: str,
    status: str,
    content: str | None = None,
    original_filename: str | None = None,
    storage_path: str | None = None,
    error_message: str | None = None,
    verified: bool = False,
) -> KnowledgeAsset:
    asset = get_by_agent_and_type(db, agent_id, asset_type)
    if asset is None:
        asset = KnowledgeAsset(agent_id=agent_id, asset_type=asset_type)
        db.add(asset)

    asset.source = source
    asset.status = status
    asset.content = content
    asset.original_filename = original_filename
    asset.storage_path = storage_path
    asset.error_message = error_message
    asset.verified = verified

    db.flush()
    return asset


def delete(db: Session, asset: KnowledgeAsset) -> None:
    db.delete(asset)
