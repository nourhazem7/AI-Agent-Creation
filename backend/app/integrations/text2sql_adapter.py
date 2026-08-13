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
from urllib.parse import quote_plus

from sqlalchemy import text as sql_text

from text2sql.agent import _get_chat_model
from text2sql.connection import Database
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

Below is the live database schema.

{schema}

Write a concise Markdown knowledge document that explains, in plain business language:
- What this database appears to be for (infer from table/column names)
- The main business entities (one short paragraph each) and which tables represent them
- Any relationships between entities that matter for answering business questions
- Terminology or naming quirks a business user should know about (e.g. abbreviated column names)

Do not invent data or business rules that aren't evidenced by the schema. If something is \
ambiguous, say so rather than guessing confidently. Return only the Markdown document."""


def generate_documentation(model: str, schema_summary: dict) -> str:
    """One auxiliary LLM call that turns a schema into plain-language Markdown docs.
    Explicitly outside the SQL-generation agent loop — this never touches execute_sql."""
    llm = get_chat_model(model)
    prompt = _DOCUMENTATION_PROMPT.format(schema=_format_schema_for_prompt(schema_summary))
    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content
    return content if isinstance(content, str) else str(content)


_VALIDATION_QUESTIONS_PROMPT = """You are preparing validation questions to verify that an AI \
assistant correctly understands a company's database.

Database schema:
{schema}

{documentation_section}

Write {n} realistic business questions a non-technical employee might ask about this data \
(e.g. "How many orders did we get last month?"). Cover different tables/relationships where \
possible. For each question, if you can confidently determine the expected SQL query and a \
short description of the expected answer shape from the schema alone, include them — otherwise \
leave those fields empty rather than guessing.

Return ONLY a JSON array, no other text, in exactly this shape:
[
  {{"question": "...", "expected_sql": "... or null", "expected_answer": "... or null"}}
]"""


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
