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


def _connection_string(db: Session, agent: Agent) -> str:
    conn = database_connection_repository.get_by_agent(db, agent.id)
    if not conn:
        raise ValueError("Connect a database before generating knowledge assets.")
    return text2sql_adapter.connection_string_for(conn, decrypted_password(conn))


def _bump_knowledge_version(db: Session, agent: Agent) -> None:
    agent.knowledge_version += 1
    # Evict any cached TextSQL engine for this agent — its documentation (metadata_hint)
    # or schema-dependent behavior just changed, so chat must rebuild on next use.
    text2sql_adapter.invalidate_engine(agent.id)
    _maybe_advance_to_ready_for_validation(db, agent)


def _maybe_advance_to_ready_for_validation(db: Session, agent: Agent) -> None:
    """Called every time a knowledge asset write succeeds — the one real, non-arbitrary
    signal that the agent has what it needs for validation. Forward-only: never regresses an
    agent that's already moved past this point (e.g. re-generating an asset on an already
    validated/active agent doesn't demote it)."""
    if agent.status in ("ready_for_validation", "validated", "active"):
        return
    assets = knowledge_asset_repository.list_by_agent(db, agent.id)
    ready_types = {a.asset_type for a in assets if a.status == "ready"}
    if ready_types >= set(ASSET_TYPES):
        agent.status = "ready_for_validation"


# ── Schema: deterministic introspection, never LLM-generated, verified before "ready" ──────


def generate_schema_asset(db: Session, agent: Agent) -> KnowledgeAsset:
    try:
        conn_str = _connection_string(db, agent)
        schema = text2sql_adapter.introspect_schema(conn_str)
        content = json.dumps(schema, indent=2)

        # Verify: round-trip the JSON we're about to store, then diff it against a SECOND,
        # independent live introspection call. Catches serialization bugs and schema drift —
        # "ready" is never set on the strength of a single unverified read.
        roundtripped = json.loads(content)
        discrepancies = text2sql_adapter.verify_schema_against_live(roundtripped, conn_str)
        if discrepancies:
            asset = knowledge_asset_repository.upsert(
                db,
                agent_id=agent.id,
                asset_type="schema",
                source="generated",
                status="error",
                error_message="Schema verification against the live database failed:\n"
                + "\n".join(discrepancies),
            )
            db.commit()
            return asset

        asset = knowledge_asset_repository.upsert(
            db,
            agent_id=agent.id,
            asset_type="schema",
            source="generated",
            status="ready",
            content=content,
            verified=True,
        )
    except Exception as exc:  # noqa: BLE001 - surface the real failure, never fake success
        asset = knowledge_asset_repository.upsert(
            db, agent_id=agent.id, asset_type="schema", source="generated", status="error", error_message=str(exc)
        )
        db.commit()
        return asset

    _bump_knowledge_version(db, agent)
    db.commit()
    db.refresh(asset)
    return asset


# ── Documentation: LLM-written, but grounded — every `table`/`table.column` reference must ─
# ── actually exist, verified mechanically after generation (one bounded retry on failure) ──


def generate_documentation_asset(db: Session, agent: Agent) -> KnowledgeAsset:
    try:
        conn_str = _connection_string(db, agent)
        schema = text2sql_adapter.introspect_schema(conn_str)

        markdown: str | None = None
        unsupported: list[str] = []
        for _attempt in range(2):  # one generation + one bounded retry if grounding fails
            candidate = text2sql_adapter.generate_documentation(agent.llm_model, schema)
            unsupported = text2sql_adapter.validate_documentation_grounding(candidate, schema)
            if not unsupported:
                markdown = candidate
                break

        if markdown is None:
            raise ValueError(
                "Generated documentation referenced schema elements that don't exist in the "
                "database, and failed grounding verification again after retrying: "
                + "; ".join(unsupported)
            )

        asset = knowledge_asset_repository.upsert(
            db,
            agent_id=agent.id,
            asset_type="documentation",
            source="generated",
            status="ready",
            content=markdown,
            verified=True,
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

    _bump_knowledge_version(db, agent)
    db.commit()
    db.refresh(asset)
    return asset


# ── Validation suite: every stored auto-generated test must have expected_sql that actually ─
# ── executes against the connected database. Unvalidated candidates are dropped, not stored ─


def _validate_candidates(conn_str: str, candidates: list[dict], exclude: set[str] | None = None) -> list[dict]:
    exclude = exclude or set()
    verified = []
    for item in candidates:
        if item["question"] in exclude:
            continue
        sql = item.get("expected_sql")
        if not sql:
            # No SQL means nothing to validate — per spec, auto-generated tests are stored
            # only if their SQL passes validation, so this candidate is dropped.
            continue
        ok, _error = text2sql_adapter.validate_sql_against_db(conn_str, sql)
        if ok:
            verified.append({**item, "sql_verified": True})
    return verified


def generate_validation_suite_asset(db: Session, agent: Agent, n: int = 8) -> KnowledgeAsset:
    try:
        conn_str = _connection_string(db, agent)
        schema = text2sql_adapter.introspect_schema(conn_str)
        doc_asset = get_asset(db, agent.id, "documentation")
        documentation = doc_asset.content if doc_asset and doc_asset.status == "ready" else None

        # Ask for more than needed since some candidates won't validate against the real DB.
        candidates = text2sql_adapter.generate_validation_questions(
            agent.llm_model, schema, documentation, n=n + 4
        )
        verified = _validate_candidates(conn_str, candidates)

        if len(verified) < n:
            # Prefer regenerating the shortfall over accepting what we have — bounded to one
            # retry batch, not an unbounded loop.
            shortfall = n - len(verified)
            retry_candidates = text2sql_adapter.generate_validation_questions(
                agent.llm_model, schema, documentation, n=shortfall + 3
            )
            already = {v["question"] for v in verified}
            verified.extend(_validate_candidates(conn_str, retry_candidates, exclude=already))

        verified = verified[:n]

        if not verified:
            raise ValueError(
                "None of the generated validation questions produced SQL that actually executes "
                "against the connected database, even after retrying."
            )

        asset = knowledge_asset_repository.upsert(
            db,
            agent_id=agent.id,
            asset_type="validation_suite",
            source="generated",
            status="ready",
            content=json.dumps(verified, indent=2),
            verified=True,
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

    _bump_knowledge_version(db, agent)
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


def _verify_uploaded_validation_items(conn_str: str | None, items: list[dict]) -> list[dict]:
    """Validate each uploaded test's expected_sql (when supplied) against the real database.
    Unlike auto-generated candidates, uploaded questions are never dropped — they're
    user-authored intent. An expected_sql that fails to execute is cleared (not silently kept
    as if trustworthy) and the item is marked sql_verified=False so the UI can flag it."""
    result = []
    for item in items:
        sql = item.get("expected_sql")
        verified = False
        if sql and conn_str:
            ok, _error = text2sql_adapter.validate_sql_against_db(conn_str, sql)
            if ok:
                verified = True
            else:
                item = {**item, "expected_sql": None}
        result.append({**item, "sql_verified": verified})
    return result


def _handle_schema_upload(db: Session, agent: Agent, content: bytes) -> tuple[str, bool]:
    """Schema uploads are stored as-is (JSON schema dump or raw SQL DDL). When the upload is
    valid JSON in our schema shape, cross-check it against the connected database and reject
    it outright if it doesn't match — never silently accept a schema that contradicts the
    actual database. Raw SQL DDL text can't be cross-validated without a full SQL parser, so
    it's accepted as-is (same as before) — that's the "where appropriate" boundary.

    Returns (content, verified) — verified is True only when the upload was actually
    cross-checked against a live, connected database and matched."""
    text_content = content.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text_content)
    except json.JSONDecodeError:
        return text_content, False

    if not isinstance(parsed, dict):
        return text_content, False

    try:
        conn_str = _connection_string(db, agent)
    except ValueError:
        return text_content, False  # no DB connected yet — can't verify, accept as-is

    discrepancies = text2sql_adapter.verify_schema_against_live(parsed, conn_str)
    if discrepancies:
        raise ValueError(
            "Uploaded schema does not match the connected database:\n" + "\n".join(discrepancies)
        )
    return text_content, True


def upload_asset(db: Session, agent: Agent, asset_type: str, filename: str, content: bytes) -> KnowledgeAsset:
    if asset_type not in ASSET_TYPES:
        raise ValueError(f"Unknown asset type: {asset_type}")

    storage_path = _save_raw_file(agent.id, asset_type, filename, content)
    verified = False

    if asset_type == "validation_suite":
        questions = _parse_validation_suite_upload(filename, content)
        try:
            conn_str = _connection_string(db, agent)
        except ValueError:
            conn_str = None
        questions = _verify_uploaded_validation_items(conn_str, questions)
        asset_content = json.dumps(questions, indent=2)
        # _verify_uploaded_validation_items already ran the real verification pass (each
        # item's expected_sql checked against the live database) — the asset-level flag
        # should reflect that, the same way generate_validation_suite_asset does. Without
        # this, _sync_from_knowledge_asset's `asset.verified` gate never passes for an
        # uploaded suite, so the uploaded questions would never become ValidationTest rows.
        verified = True
    elif asset_type == "schema":
        asset_content, verified = _handle_schema_upload(db, agent, content)
    else:
        # documentation: stored as-is (rendered safely as Markdown text on the frontend —
        # never as raw HTML, so there is no injection surface).
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
        verified=verified,
    )
    _bump_knowledge_version(db, agent)
    db.commit()
    db.refresh(asset)
    return asset


def delete_asset(db: Session, agent: Agent, asset_type: str) -> None:
    asset = knowledge_asset_repository.get_by_agent_and_type(db, agent.id, asset_type)
    if asset:
        knowledge_asset_repository.delete(db, asset)
        _bump_knowledge_version(db, agent)
        db.commit()
