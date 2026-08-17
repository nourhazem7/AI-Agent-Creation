"""Response shapes for the Knowledge Summary — answers "what does this agent currently know
about my database?" using only verified Knowledge Assets and live database metadata. No
field here is ever populated by a fresh, unverified LLM call — see knowledge_summary_service.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ColumnFact(BaseModel):
    name: str
    type: str
    nullable: bool
    is_primary_key: bool


class ForeignKeyFact(BaseModel):
    columns: list[str]
    referred_table: str
    referred_columns: list[str]


class TableFact(BaseModel):
    name: str
    columns: list[ColumnFact]
    primary_keys: list[str]
    foreign_keys: list[ForeignKeyFact]


class DatabaseFacts(BaseModel):
    """Category 1: facts directly verified from the database/schema — never inferred."""

    connected: bool
    dialect: str | None = None
    table_count: int = 0
    tables: list[TableFact] = Field(default_factory=list)
    relationship_count: int = 0
    # Whether these facts came from a live introspection just now, or (DB not currently
    # connected) from the last stored, previously-verified schema asset.
    source: str = "none"  # "live" | "stored_schema_asset" | "none"
    # If a schema knowledge asset exists, whether it still matches the live database right
    # now (re-checked on every summary load) — an honest staleness signal, not a guess.
    schema_asset_matches_live: bool | None = None


class DocumentationSummary(BaseModel):
    """Category 2: what the documentation asset says — displayed as-is, never re-summarized
    by a fresh LLM call. `verified` reflects whether it actually passed grounding checks."""

    configured: bool
    status: str = "not_configured"
    source: str | None = None
    verified: bool = False
    content: str | None = None
    word_count: int = 0


class ValidationCoverage(BaseModel):
    """Category 3: validation coverage from the staged validation-suite knowledge asset."""

    configured: bool
    status: str = "not_configured"
    source: str | None = None
    total_tests: int = 0
    sql_verified_count: int = 0


class KnowledgeReadiness(BaseModel):
    ready_count: int
    total_count: int
    all_ready: bool


class KnowledgeSummaryOut(BaseModel):
    agent_id: str
    agent_name: str
    database: DatabaseFacts
    documentation: DocumentationSummary
    validation: ValidationCoverage
    readiness: KnowledgeReadiness
