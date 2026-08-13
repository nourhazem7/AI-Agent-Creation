from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrations import text2sql_adapter
from app.models.agent import Agent
from app.models.knowledge_asset import ASSET_TYPES, KnowledgeAsset
from app.repositories import database_connection_repository, knowledge_asset_repository
from app.services.database_connection_service import decrypted_password

settings = get_settings()


def list_assets(db: Session, agent_id: str) -> list[KnowledgeAsset]:
    return knowledge_asset_repository.list_by_agent(db, agent_id)


def get_asset(db: Session, agent_id: str, asset_type: str) -> KnowledgeAsset | None:
    return knowledge_asset_repository.get_by_agent_and_type(db, agent_id, asset_type)


def _live_schema_summary(db: Session, agent: Agent) -> dict:
    conn = database_connection_repository.get_by_agent(db, agent.id)
    if not conn:
        raise ValueError("Connect a database before generating knowledge assets.")
    conn_str = text2sql_adapter.connection_string_for(conn, decrypted_password(conn))
    return text2sql_adapter.introspect_schema(conn_str)


def _bump_knowledge_version(agent: Agent) -> None:
    agent.knowledge_version += 1


def generate_schema_asset(db: Session, agent: Agent) -> KnowledgeAsset:
    try:
        schema = _live_schema_summary(db, agent)
        asset = knowledge_asset_repository.upsert(
            db,
            agent_id=agent.id,
            asset_type="schema",
            source="generated",
            status="ready",
            content=json.dumps(schema, indent=2),
        )
    except Exception as exc:  # noqa: BLE001 - surface the real failure, never fake success
        asset = knowledge_asset_repository.upsert(
            db, agent_id=agent.id, asset_type="schema", source="generated", status="error", error_message=str(exc)
        )
        db.commit()
        return asset

    _bump_knowledge_version(agent)
    db.commit()
    db.refresh(asset)
    return asset


def generate_documentation_asset(db: Session, agent: Agent) -> KnowledgeAsset:
    try:
        schema = _live_schema_summary(db, agent)
        markdown = text2sql_adapter.generate_documentation(agent.llm_model, schema)
        asset = knowledge_asset_repository.upsert(
            db, agent_id=agent.id, asset_type="documentation", source="generated", status="ready", content=markdown
        )
    except Exception as exc:  # noqa: BLE001
        asset = knowledge_asset_repository.upsert(
            db,
            agent_id=agent.id,
            asset_type="documentation",
            source="generated",
            status="error",
            error_message=str(exc),
        )
        db.commit()
        return asset

    _bump_knowledge_version(agent)
    db.commit()
    db.refresh(asset)
    return asset


def generate_validation_suite_asset(db: Session, agent: Agent, n: int = 8) -> KnowledgeAsset:
    try:
        schema = _live_schema_summary(db, agent)
        doc_asset = get_asset(db, agent.id, "documentation")
        documentation = doc_asset.content if doc_asset and doc_asset.status == "ready" else None

        questions = text2sql_adapter.generate_validation_questions(agent.llm_model, schema, documentation, n=n)
        if not questions:
            raise ValueError("The model didn't return any usable validation questions. Try again.")

        asset = knowledge_asset_repository.upsert(
            db,
            agent_id=agent.id,
            asset_type="validation_suite",
            source="generated",
            status="ready",
            content=json.dumps(questions, indent=2),
        )
    except Exception as exc:  # noqa: BLE001
        asset = knowledge_asset_repository.upsert(
            db,
            agent_id=agent.id,
            asset_type="validation_suite",
            source="generated",
            status="error",
            error_message=str(exc),
        )
        db.commit()
        return asset

    _bump_knowledge_version(agent)
    db.commit()
    db.refresh(asset)
    return asset


GENERATORS = {
    "schema": generate_schema_asset,
    "documentation": generate_documentation_asset,
    "validation_suite": generate_validation_suite_asset,
}


def generate_asset(db: Session, agent: Agent, asset_type: str) -> KnowledgeAsset:
    if asset_type not in ASSET_TYPES:
        raise ValueError(f"Unknown asset type: {asset_type}")
    return GENERATORS[asset_type](db, agent)


# ── Uploads ──────────────────────────────────────────────────────────────────


def _save_raw_file(agent_id: str, asset_type: str, filename: str, content: bytes) -> str:
    safe_name = Path(filename).name
    target_dir = Path(settings.storage_dir) / "uploads" / agent_id / asset_type
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / safe_name
    target_path.write_bytes(content)
    return str(target_path.resolve())


def _parse_validation_suite_upload(filename: str, content: bytes) -> list[dict]:
    text = content.decode("utf-8", errors="replace")
    lower_name = filename.lower()

    if lower_name.endswith(".json"):
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("Expected a JSON array of {question, expected_sql?, expected_answer?} objects.")
        items = data
    elif lower_name.endswith(".csv"):
        reader = csv.DictReader(io.StringIO(text))
        items = list(reader)
    else:
        raise ValueError("Upload a .json or .csv file of test cases.")

    results = []
    for item in items:
        question = (item.get("question") or "").strip() if isinstance(item, dict) else ""
        if not question:
            continue
        results.append(
            {
                "question": question,
                "expected_sql": (item.get("expected_sql") or None) if isinstance(item, dict) else None,
                "expected_answer": (item.get("expected_answer") or None) if isinstance(item, dict) else None,
            }
        )
    if not results:
        raise ValueError("No valid rows found — each row needs at least a 'question'.")
    return results


def upload_asset(db: Session, agent: Agent, asset_type: str, filename: str, content: bytes) -> KnowledgeAsset:
    if asset_type not in ASSET_TYPES:
        raise ValueError(f"Unknown asset type: {asset_type}")

    storage_path = _save_raw_file(agent.id, asset_type, filename, content)

    if asset_type == "validation_suite":
        questions = _parse_validation_suite_upload(filename, content)
        asset_content = json.dumps(questions, indent=2)
    else:
        # schema and documentation uploads are stored as-is (JSON/SQL DDL, or Markdown/text).
        asset_content = content.decode("utf-8", errors="replace")

    asset = knowledge_asset_repository.upsert(
        db,
        agent_id=agent.id,
        asset_type=asset_type,
        source="uploaded",
        status="ready",
        content=asset_content,
        original_filename=filename,
        storage_path=storage_path,
    )
    _bump_knowledge_version(agent)
    db.commit()
    db.refresh(asset)
    return asset


def delete_asset(db: Session, agent: Agent, asset_type: str) -> None:
    asset = knowledge_asset_repository.get_by_agent_and_type(db, agent.id, asset_type)
    if asset:
        knowledge_asset_repository.delete(db, asset)
        _bump_knowledge_version(agent)
        db.commit()
