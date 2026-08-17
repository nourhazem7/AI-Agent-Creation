"""The only module that imports from `text2sql`.

Everything else in Agent One talks to the reasoning engine through this adapter —
never directly. Built out incrementally:
  - Milestone 4: connection-string building + test_connection
  - Milestone 5: schema introspection + documentation/validation-question generation
    (auxiliary one-off LLM calls, outside the SQL-generation agent loop)
  - Milestone 6: cached TextSQL engine construction + ask/stream_ask (the actual
    agentic SQL loop, used by chat and validation-test runs)

`text2sql` itself is never modified — see text2sql-framework/text2sql-framework-main/.
"""

from __future__ import annotations

import json
import re
import threading
from typing import Iterator
from urllib.parse import quote_plus

from sqlalchemy import text as sql_text

from text2sql import TextSQL
from text2sql.agent import _get_chat_model
from text2sql.connection import Database
from text2sql.tools import _is_read_only
from langchain_core.messages import HumanMessage

from app.config import get_settings
from app.models.database_connection import DatabaseConnection

settings = get_settings()


def get_chat_model(model: str | None = None):
    """The one place that constructs an LLM client, so every caller — the auxiliary
    generation calls below AND (from Milestone 6) the actual TextSQL engine construction
    — consistently gets the company's configured endpoint (base_url/verify_ssl/extra_body/
    llm_api_key), not just a bare model name relying on ambient env vars.

    `model` defaults to settings.llm_model (the configured company model) when not given;
    callers may still pass a different 'provider:model' string per agent if ever needed.
    """
    return _get_chat_model(
        model or settings.llm_model,
        base_url=settings.llm_base_url or None,
        verify_ssl=settings.llm_verify_ssl,
        extra_body=settings.llm_extra_body_dict,
        llm_api_key=settings.llm_api_key or None,
    )


# ── Cached TextSQL engines — the actual agentic SQL loop, used by chat + validation runs ───
#
# Keyed on (agent_id, knowledge_version). agent_id makes cross-agent reuse structurally
# impossible (it's the dict key itself — Agent A can never look up Agent B's entry).
# knowledge_version (bumped by the service layer on every DB-connection or knowledge-asset
# change) makes the SAME agent get a fresh engine whenever its own config changes, rather
# than silently answering questions with a stale schema/connection/instructions.
_engine_cache: dict[tuple[str, int], TextSQL] = {}
_engine_cache_lock = threading.Lock()


def get_engine(
    *,
    agent_id: str,
    knowledge_version: int,
    llm_model: str,
    connection_string: str,
    custom_instructions: str | None = None,
    metadata_hint: str | None = None,
    trace_file: str | None = None,
) -> TextSQL:
    """Build (or reuse) the TextSQL engine for one specific agent's current configuration.

    Never pass api_key=/api_url= to TextSQL — that path POSTs traces to a third-party
    dashboard (text2sql/tracing.py); trace_file= keeps traces local to this deployment.
    """
    cache_key = (agent_id, knowledge_version)

    with _engine_cache_lock:
        cached = _engine_cache.get(cache_key)
        if cached is not None:
            return cached

    engine = TextSQL(
        connection_string,
        model=llm_model,
        instructions=custom_instructions,
        metadata_hint=metadata_hint,
        trace_file=trace_file,
        base_url=settings.llm_base_url or None,
        verify_ssl=settings.llm_verify_ssl,
        extra_body=settings.llm_extra_body_dict,
        llm_api_key=settings.llm_api_key or None,
    )

    with _engine_cache_lock:
        # Another thread may have built and cached one concurrently — keep whichever
        # landed first so a single agent+version never has two live engine instances.
        _engine_cache.setdefault(cache_key, engine)
        return _engine_cache[cache_key]


def invalidate_engine(agent_id: str) -> None:
    """Evict every cached engine for this agent (all knowledge_version entries). Called
    whenever the agent's DB connection or knowledge assets change (new knowledge_version
    means a new cache key anyway, but this also frees the now-orphaned old entry) and when
    the agent itself is deleted."""
    with _engine_cache_lock:
        for key in [k for k in _engine_cache if k[0] == agent_id]:
            del _engine_cache[key]


def ask(engine: TextSQL, question: str, max_rows: int | None = None):
    """Run the real agentic SQL loop. Returns a text2sql.SQLResult."""
    return engine.ask(question, max_rows=max_rows)


def stream_ask(engine: TextSQL, question: str, max_rows: int | None = None) -> Iterator[tuple[str, dict]]:
    """Stream the agentic SQL loop's progress. Yields ('step'|'step_result', payload) events
    with safe, high-level labels (e.g. "Exploring database schema") — no chain-of-thought —
    then a final ('result', SQLResult). `engine.generator` is the SQLGenerator instance
    TextSQL assigns itself in __init__ (text2sql/core.py); TextSQL doesn't expose stream_ask
    directly, so this is the supported way to reach it without modifying text2sql.
    """
    yield from engine.generator.stream_ask(question, max_rows=max_rows)


# Dialect -> SQLAlchemy driver. Only dialects with a driver actually installed
# (backend/requirements.txt) belong here — see models/database_connection.py's
# SUPPORTED_DIALECTS, which the API layer enforces before this is ever called.
_DRIVER_BY_DIALECT = {
    "postgresql": "postgresql+psycopg2",
    "mysql": "mysql+pymysql",
    "mssql": "mssql+pyodbc",
}


def build_connection_string(
    *,
    dialect: str,
    host: str | None = None,
    port: int | None = None,
    database_name: str | None = None,
    username: str | None = None,
    password: str | None = None,
    sqlite_file_path: str | None = None,
) -> str:
    """Build a SQLAlchemy connection string for a dialect. Never logs the result (it may
    contain a plaintext password) — callers must treat the return value as a secret."""
    if dialect == "sqlite":
        if not sqlite_file_path:
            raise ValueError("sqlite_file_path is required for the sqlite dialect")
        return f"sqlite:///{sqlite_file_path}"

    driver = _DRIVER_BY_DIALECT.get(dialect)
    if not driver:
        raise ValueError(f"Unsupported dialect: {dialect}")

    auth = ""
    if username:
        auth = quote_plus(username)
        if password:
            auth += f":{quote_plus(password)}"
        auth += "@"

    netloc = host or ""
    if port:
        netloc += f":{port}"

    path = f"/{database_name}" if database_name else ""

    conn_str = f"{driver}://{auth}{netloc}{path}"
    if dialect == "mssql":
        conn_str += "?driver=ODBC+Driver+17+for+SQL+Server"
    return conn_str


def test_connection(connection_string: str) -> tuple[bool, str | None]:
    """Try to connect and run a trivial query. Returns (ok, error_message).

    Deliberately does NOT call Database.test_connection() — that method (text2sql/
    connection.py) catches every exception internally and returns a bare bool, which
    would hide the actual driver error from the user. Using Database.engine directly
    (a public attribute set in Database.__init__) gets the same behavior plus the
    real message, without modifying text2sql.
    """
    try:
        db = Database(connection_string)
        with db.engine.connect() as conn:
            conn.execute(sql_text("SELECT 1"))
        return True, None
    except Exception as exc:  # noqa: BLE001 - surfacing the real driver error is the point
        return False, str(exc)


def connection_string_for(conn: DatabaseConnection, decrypted_password: str | None) -> str:
    """Build the connection string for a persisted DatabaseConnection row."""
    return build_connection_string(
        dialect=conn.dialect,
        host=conn.host,
        port=conn.port,
        database_name=conn.database_name,
        username=conn.username,
        password=decrypted_password,
        sqlite_file_path=conn.sqlite_file_path,
    )


def introspect_schema(connection_string: str) -> dict:
    """Return the live schema summary (tables/columns/keys/FKs) for a connection.

    Wraps Database.get_schema_summary() — the single source of truth for both the
    "generate schema asset" action and the Knowledge Summary page's stats, so those
    numbers can never drift from what the database actually contains.
    """
    db = Database(connection_string)
    return db.get_schema_summary()


def verify_schema_against_live(candidate_schema: dict, connection_string: str) -> list[str]:
    """Structurally compare a schema (already introspected + JSON round-tripped) against
    a FRESH second live introspection call. Returns a list of discrepancy strings — empty
    means it matches. This is what "ready" is conditioned on for the schema asset: never
    LLM-generated, always re-verified against actual database metadata before being trusted.
    """
    live = introspect_schema(connection_string)
    issues: list[str] = []

    candidate_tables = set(candidate_schema.keys())
    live_tables = set(live.keys())

    for missing in sorted(live_tables - candidate_tables):
        issues.append(f"Table '{missing}' exists in the database but is missing from the generated schema.")
    for extra in sorted(candidate_tables - live_tables):
        issues.append(f"Table '{extra}' appears in the generated schema but does not exist in the database.")

    for table in sorted(candidate_tables & live_tables):
        cand_cols = {c["name"]: c for c in candidate_schema[table].get("columns", [])}
        live_cols = {c["name"]: c for c in live[table].get("columns", [])}

        for missing in sorted(set(live_cols) - set(cand_cols)):
            issues.append(f"Column '{table}.{missing}' exists in the database but is missing from the generated schema.")
        for extra in sorted(set(cand_cols) - set(live_cols)):
            issues.append(f"Column '{table}.{extra}' appears in the generated schema but does not exist in the database.")

        for col in sorted(set(cand_cols) & set(live_cols)):
            if str(cand_cols[col].get("type")) != str(live_cols[col].get("type")):
                issues.append(
                    f"Column '{table}.{col}' type mismatch: generated says "
                    f"'{cand_cols[col].get('type')}', database says '{live_cols[col].get('type')}'."
                )

        cand_pk = set(candidate_schema[table].get("primary_keys") or [])
        live_pk = set(live[table].get("primary_keys") or [])
        if cand_pk != live_pk:
            issues.append(f"Table '{table}' primary key mismatch: generated {sorted(cand_pk)}, database {sorted(live_pk)}.")

        def _fk_set(fks):
            return {
                (tuple(fk.get("constrained_columns") or []), fk.get("referred_table"), tuple(fk.get("referred_columns") or []))
                for fk in fks
            }

        cand_fks = _fk_set(candidate_schema[table].get("foreign_keys") or [])
        live_fks = _fk_set(live[table].get("foreign_keys") or [])
        if cand_fks != live_fks:
            issues.append(f"Table '{table}' foreign key mismatch: generated {cand_fks}, database {live_fks}.")

    return issues


def _format_schema_for_prompt(schema: dict) -> str:
    """Render a schema summary dict as compact text for an LLM prompt.
    (Same shape as text2sql/generate.py's private _format_schema_for_prompt — reimplemented
    here rather than imported since that helper is a private, unexported function.)
    """
    lines = []
    for table, info in schema.items():
        comment = f"  -- {info['comment']}" if info.get("comment") else ""
        lines.append(f"Table: {table}{comment}")
        for col in info["columns"]:
            nullable = "" if col["nullable"] else " NOT NULL"
            col_comment = f"  -- {col['comment']}" if col.get("comment") else ""
            lines.append(f"  {col['name']}  {col['type']}{nullable}{col_comment}")
        if info.get("primary_keys"):
            lines.append(f"  PK: {', '.join(info['primary_keys'])}")
        for fk in info.get("foreign_keys", []):
            cols = ", ".join(fk["constrained_columns"])
            ref_cols = ", ".join(fk["referred_columns"])
            lines.append(f"  FK: {cols} -> {fk['referred_table']}({ref_cols})")
        lines.append("")
    return "\n".join(lines)


_DOCUMENTATION_PROMPT = """You are documenting a company's database for a non-technical business \
user who will later ask an AI assistant questions about this data in plain English.

Below is the live, actual database schema. It is your ONLY source of truth — you have no other \
information about this company, its policies, or its business rules.

{schema}

Write a concise Markdown knowledge document that explains, in plain business language:
- What this database appears to be for (infer from table/column names)
- The main business entities (one short paragraph each) and which tables represent them
- Any relationships between entities that matter for answering business questions (only ones \
that are actually foreign keys in the schema above)
- Terminology or naming quirks a business user should know about (e.g. abbreviated column names)

STRICT GROUNDING RULES — these will be automatically checked, so follow them exactly:
1. Every time you name a specific table or column, wrap it in backticks, e.g. `employees` or \
`employees.department_id`. Only use backticks for real table/column names from the schema above \
— never for anything else.
2. Do not invent tables, columns, or relationships that are not in the schema above.
3. Do not invent business rules, company policies, metrics, or facts that are not directly \
evidenced by the schema (e.g. do NOT say "reviews happen quarterly" or "employees must complete \
onboarding within 30 days" unless a table/column literally represents that).
4. Clearly separate three kinds of statements as you write:
   - Structural facts directly observed from the schema (e.g. "`employees` has a foreign key to \
`departments` via `department_id`").
   - Reasonable descriptions of what a table/column represents, based on its name (e.g. \
"`hire_date` likely records when the employee joined").
   - Business interpretations inferred from naming patterns — mark these explicitly as \
inferred/likely, not as settled fact (e.g. "this appears to be an HR system, based on table names").
5. If something is ambiguous, say so rather than guessing confidently.

Return only the Markdown document."""


def generate_documentation(model: str, schema_summary: dict) -> str:
    """One auxiliary LLM call that turns a schema into plain-language Markdown docs.
    Explicitly outside the SQL-generation agent loop — this never touches execute_sql.
    Callers must run validate_documentation_grounding() on the result before trusting it —
    this function only generates; it does not verify."""
    llm = get_chat_model(model)
    prompt = _DOCUMENTATION_PROMPT.format(schema=_format_schema_for_prompt(schema_summary))
    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content
    return content if isinstance(content, str) else str(content)


_BACKTICK_REF = re.compile(r"`([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)`")

# SQL data types and keywords the LLM legitimately formats in backticks when describing a
# column (e.g. "`hire_date` is a `DATE`") — these are not schema-element claims and must not
# be flagged as invented. Real table/column names in every schema this framework introspects
# are lowercase snake_case (SQLAlchemy/DB convention), so in practice a simple, robust rule
# is: an all-uppercase token is a type/keyword, never a real identifier. Named explicitly too,
# belt-and-braces, in case a type name is written in mixed case.
_SQL_TYPE_AND_KEYWORDS = {
    "INTEGER", "INT", "TEXT", "REAL", "BLOB", "NUMERIC", "VARCHAR", "CHAR", "BOOLEAN", "BOOL",
    "DATE", "TIME", "DATETIME", "TIMESTAMP", "FLOAT", "DOUBLE", "DECIMAL", "BIGINT", "SMALLINT",
    "NULL", "TRUE", "FALSE", "SELECT", "FROM", "WHERE", "JOIN", "GROUP", "ORDER", "BY", "AND",
    "OR", "NOT", "IN", "AS", "ON", "LEFT", "RIGHT", "INNER", "OUTER", "PRIMARY", "KEY", "FOREIGN",
    "REFERENCES", "DISTINCT", "LIMIT",
}


def _looks_like_type_or_keyword(token: str) -> bool:
    return token.upper() == token or token.upper() in _SQL_TYPE_AND_KEYWORDS


def validate_documentation_grounding(markdown: str, schema: dict) -> list[str]:
    """Extract every backtick-wrapped `table` / `table.column` reference from generated
    documentation and verify each one actually exists in the live schema. Returns a list of
    unsupported references — empty means every claim the doc made about the schema is real.

    This only checks structural references (table/column names), which is what's mechanically
    verifiable. It cannot verify prose business claims — the prompt's grounding rules are the
    (unverifiable) defense against those; this function is the (verifiable) defense against
    invented schema elements specifically. SQL types/keywords in backticks (e.g. `DATE`,
    `SELECT`) are ignored — they're formatting choices, not schema claims.
    """
    table_names = set(schema.keys())
    column_names_by_table = {t: {c["name"] for c in info.get("columns", [])} for t, info in schema.items()}
    all_column_names = {c for cols in column_names_by_table.values() for c in cols}

    unsupported: list[str] = []
    seen: set[str] = set()
    for ref in _BACKTICK_REF.findall(markdown):
        if ref in seen:
            continue
        seen.add(ref)

        if "." in ref:
            table, column = ref.split(".", 1)
            if _looks_like_type_or_keyword(table) or _looks_like_type_or_keyword(column):
                continue
            if table not in table_names:
                unsupported.append(f"`{ref}` — table '{table}' does not exist")
            elif column not in column_names_by_table.get(table, set()):
                unsupported.append(f"`{ref}` — column '{column}' does not exist on table '{table}'")
        else:
            if _looks_like_type_or_keyword(ref):
                continue
            if ref not in table_names and ref not in all_column_names:
                unsupported.append(f"`{ref}` — not a real table or column name")

    return unsupported


_VALIDATION_QUESTIONS_PROMPT = """You are preparing validation questions to verify that an AI \
assistant correctly understands a company's database.

Database schema:
{schema}

{documentation_section}

Write {n} realistic business questions a non-technical employee might ask about this data \
(e.g. "How many orders did we get last month?"). Cover different tables/relationships where \
possible — prefer questions that require joining multiple tables over single-table questions, \
since those better test whether the schema is actually understood. Use ONLY exact table/column \
names from the schema above.

For each question, do your best to write the expected SQL query and a short description of the \
expected answer shape, using only real table/column names from the schema. Every expected_sql \
you provide will be executed against the real database and discarded if it fails, so attempt it \
even if not fully certain — but leave expected_sql null rather than guessing at table/column \
names that aren't in the schema above.

Return ONLY a JSON array, no other text, in exactly this shape:
[
  {{"question": "...", "expected_sql": "... or null", "expected_answer": "... or null"}}
]"""


def validate_sql_against_db(connection_string: str, sql: str) -> tuple[bool, str | None]:
    """Actually execute a candidate SQL statement read-only against the real database.
    Returns (ok, error_message). Used to verify every auto-generated (and, when supplied,
    uploaded) validation test's expected_sql really runs — never store an unexecuted guess
    as if it were a verified expected answer.

    Reuses text2sql.tools._is_read_only (the framework's own destructive-statement guard)
    rather than reimplementing SQL safety checking — this is auxiliary verification tooling,
    not the SQL-generation path, so it isn't going through text2sql's execute_sql tool, but
    it must honor the same read-only guarantee before touching a real database.
    """
    if not sql or not sql.strip():
        return False, "No SQL to validate."
    if not _is_read_only(sql):
        return False, "Rejected: only read-only SQL (SELECT/WITH/EXPLAIN/SHOW/DESCRIBE/PRAGMA) is allowed."
    try:
        db = Database(connection_string)
        db.execute(sql)
        return True, None
    except Exception as exc:  # noqa: BLE001 - the real DB error is exactly what callers need
        return False, str(exc)


def get_reference_result(connection_string: str, sql: str) -> tuple[list[dict] | None, str | None]:
    """Execute a read-only reference/expected SQL query and return its rows. Same read-only
    guard as validate_sql_against_db, but returns the actual data — used by the validation
    workspace to compare an agent's own generated SQL's output against an expected_sql's
    output, not just check that the expected_sql runs at all."""
    if not sql or not sql.strip():
        return None, "No SQL to execute."
    if not _is_read_only(sql):
        return None, "Rejected: only read-only SQL (SELECT/WITH/EXPLAIN/SHOW/DESCRIBE/PRAGMA) is allowed."
    try:
        db = Database(connection_string)
        return db.execute(sql), None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def generate_validation_questions(
    model: str, schema_summary: dict, documentation: str | None = None, n: int = 8
) -> list[dict]:
    """One auxiliary LLM call producing candidate validation questions. Returns a list of
    {question, expected_sql, expected_answer} dicts — caller inserts these as ValidationTest
    rows with origin="ai_generated". Never executes SQL; purely question generation."""
    llm = get_chat_model(model)
    documentation_section = f"Documentation:\n{documentation}" if documentation else ""
    prompt = _VALIDATION_QUESTIONS_PROMPT.format(
        schema=_format_schema_for_prompt(schema_summary),
        documentation_section=documentation_section,
        n=n,
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content
    text = content if isinstance(content, str) else str(content)

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        items = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []

    results = []
    for item in items:
        if not isinstance(item, dict) or not item.get("question"):
            continue
        results.append(
            {
                "question": str(item["question"]),
                "expected_sql": item.get("expected_sql") or None,
                "expected_answer": item.get("expected_answer") or None,
            }
        )
    return results
