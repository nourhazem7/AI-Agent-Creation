"""Builds the Knowledge Summary — deterministic only. Every field is either read straight
from a stored, already-verified Knowledge Asset, or computed by live database introspection
(the exact same text2sql_adapter.introspect_schema() used everywhere else). No LLM call is
made here, and nothing is invented — see schemas/knowledge_summary.py for the category split.
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.integrations import text2sql_adapter
from app.models.agent import Agent
from app.models.knowledge_asset import ASSET_TYPES
from app.repositories import database_connection_repository, knowledge_asset_repository
from app.schemas.knowledge_summary import (
    ColumnFact,
    DatabaseFacts,
    DocumentationSummary,
    ForeignKeyFact,
    KnowledgeReadiness,
    KnowledgeSummaryOut,
    TableFact,
    ValidationCoverage,
)
from app.services.database_connection_service import decrypted_password


def _table_facts_from_schema(schema: dict) -> list[TableFact]:
    tables = []
    for name, info in schema.items():
        pk = set(info.get("primary_keys") or [])
        columns = [
            ColumnFact(
                name=col["name"],
                type=str(col.get("type", "")),
                nullable=bool(col.get("nullable", True)),
                is_primary_key=col["name"] in pk,
            )
            for col in info.get("columns", [])
        ]
        fks = [
            ForeignKeyFact(
                columns=fk.get("constrained_columns", []),
                referred_table=fk.get("referred_table", ""),
                referred_columns=fk.get("referred_columns", []),
            )
            for fk in info.get("foreign_keys", [])
        ]
        tables.append(TableFact(name=name, columns=columns, primary_keys=sorted(pk), foreign_keys=fks))
    tables.sort(key=lambda t: t.name)
    return tables


def _relationship_count(schema: dict) -> int:
    return sum(len(info.get("foreign_keys") or []) for info in schema.values())


def _build_database_facts(db: Session, agent: Agent, schema_asset) -> DatabaseFacts:
    conn = database_connection_repository.get_by_agent(db, agent.id)

    if conn and conn.is_connected:
        try:
            conn_str = text2sql_adapter.connection_string_for(conn, decrypted_password(conn))
            live_schema = text2sql_adapter.introspect_schema(conn_str)
        except Exception:  # noqa: BLE001 - connection may have gone stale since last test
            live_schema = None

        if live_schema is not None:
            matches_live: bool | None = None
            if schema_asset and schema_asset.status == "ready" and schema_asset.content:
                try:
                    stored = json.loads(schema_asset.content)
                    discrepancies = text2sql_adapter.verify_schema_against_live(stored, conn_str)
                    matches_live = not discrepancies
                except Exception:  # noqa: BLE001 - malformed stored content, just skip the cross-check
                    matches_live = None

            return DatabaseFacts(
                connected=True,
                dialect=conn.dialect,
                table_count=len(live_schema),
                tables=_table_facts_from_schema(live_schema),
                relationship_count=_relationship_count(live_schema),
                source="live",
                schema_asset_matches_live=matches_live,
            )

    # Not connected (or connection just failed) — fall back to the last stored, previously
    # verified schema asset rather than showing nothing, but label it honestly as not-live.
    if schema_asset and schema_asset.status == "ready" and schema_asset.content:
        try:
            stored = json.loads(schema_asset.content)
            if isinstance(stored, dict):
                return DatabaseFacts(
                    connected=False,
                    dialect=conn.dialect if conn else None,
                    table_count=len(stored),
                    tables=_table_facts_from_schema(stored),
                    relationship_count=_relationship_count(stored),
                    source="stored_schema_asset",
                    schema_asset_matches_live=None,
                )
        except json.JSONDecodeError:
            pass

    return DatabaseFacts(connected=bool(conn and conn.is_connected), dialect=conn.dialect if conn else None)


def _build_documentation_summary(doc_asset) -> DocumentationSummary:
    if not doc_asset:
        return DocumentationSummary(configured=False)

    content = doc_asset.content
    word_count = len(content.split()) if content else 0

    return DocumentationSummary(
        configured=True,
        status=doc_asset.status,
        source=doc_asset.source,
        verified=bool(doc_asset.verified),
        content=content,
        word_count=word_count,
    )


def _build_validation_coverage(val_asset) -> ValidationCoverage:
    if not val_asset:
        return ValidationCoverage(configured=False)

    total = 0
    sql_verified = 0
    if val_asset.content:
        try:
            items = json.loads(val_asset.content)
            if isinstance(items, list):
                total = len(items)
                sql_verified = sum(1 for item in items if isinstance(item, dict) and item.get("sql_verified") is True)
        except json.JSONDecodeError:
            pass

    return ValidationCoverage(
        configured=True,
        status=val_asset.status,
        source=val_asset.source,
        total_tests=total,
        sql_verified_count=sql_verified,
    )


def get_summary(db: Session, agent: Agent) -> KnowledgeSummaryOut:
    assets = {a.asset_type: a for a in knowledge_asset_repository.list_by_agent(db, agent.id)}
    schema_asset = assets.get("schema")
    doc_asset = assets.get("documentation")
    val_asset = assets.get("validation_suite")

    ready_count = sum(1 for a in assets.values() if a.status == "ready")

    return KnowledgeSummaryOut(
        agent_id=agent.id,
        agent_name=agent.name,
        database=_build_database_facts(db, agent, schema_asset),
        documentation=_build_documentation_summary(doc_asset),
        validation=_build_validation_coverage(val_asset),
        readiness=KnowledgeReadiness(
            ready_count=ready_count,
            total_count=len(ASSET_TYPES),
            all_ready=ready_count == len(ASSET_TYPES),
        ),
    )
