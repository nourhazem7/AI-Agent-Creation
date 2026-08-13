"""FastAPI backend for the Wedy.ai text2sql chat interface.

Endpoints
---------
GET  /health
POST /api/sessions                            create session (test DB + init engine)
GET  /api/sessions/{session_id}               session info
DELETE /api/sessions/{session_id}             remove session
GET  /api/sessions/{session_id}/schema        full schema of the connected DB
POST /api/sessions/{session_id}/ask           agentic query  (explores schema, self-corrects)
POST /api/sessions/{session_id}/write_sql     single-pass query (fast, no tool loop)

Run with:
    uvicorn text2sql.api:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pathlib import Path

from text2sql.connection import Database
from text2sql.core import TextSQL

# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Wedy.ai Text2SQL API",
    description="Natural language to SQL — powered by Wedy.ai",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static UI ─────────────────────────────────────────────────────────────────
_UI_DIR = Path(__file__).parent.parent / "ui"
if _UI_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(_UI_DIR), html=True), name="ui")

# Also serve project root as /static so the logo is reachable at /static/Wedy.ai Logo.jpg
_ROOT_DIR = Path(__file__).parent.parent
app.mount("/static", StaticFiles(directory=str(_ROOT_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def root_redirect():
    """Redirect browser root to the UI."""
    return RedirectResponse(url="/ui/index.html")

# ── In-memory session store ───────────────────────────────────────────────────
# session_id  ->  {"engine": TextSQL, "dialect": str, "tables": list, ...}
_sessions: dict[str, dict[str, Any]] = {}


# ── Request / Response schemas ────────────────────────────────────────────────

class ConnectRequest(BaseModel):
    connection_string: str = Field(
        ...,
        example="sqlite:///company.db",
        description="Any SQLAlchemy-supported connection string.",
    )
    model: str = Field(
        default="openai:Qwen/Qwen3.6-35B-A3B",
        description="'provider:model_name' — openai or anthropic.",
    )
    base_url: str | None = Field(
        default="https://ibm-models.elsewedy-ec.com/v1",
        description="Override API base URL for on-prem / vLLM endpoints.",
    )
    verify_ssl: bool = Field(
        default=False,
        description="Set False to skip TLS verification (self-signed certs).",
    )
    extra_body: dict | None = Field(
        default={"chat_template_kwargs": {"enable_thinking": False}},
        description="Extra JSON fields merged into every LLM request body.",
    )
    llm_api_key: str | None = Field(
        default=None,
        description="API key for the LLM endpoint (falls back to env var).",
    )
    instructions: str | None = Field(
        default=None,
        description="Domain-specific instructions injected into the system prompt.",
    )


class ConnectResponse(BaseModel):
    session_id: str
    dialect: str
    table_count: int
    tables: list[str]
    message: str


class AskRequest(BaseModel):
    question: str = Field(..., description="Natural language question about the database.")
    max_rows: int | None = Field(default=100, description="Max rows to return.")


class WriteSQLRequest(BaseModel):
    question: str = Field(..., description="Natural language question about the database.")
    execute: bool = Field(default=True, description="Execute the generated SQL.")
    max_rows: int | None = Field(default=100, description="Max rows to return.")


class QueryResponse(BaseModel):
    question: str
    sql: str
    data: list[dict] = Field(default_factory=list)
    error: str | None = None
    commentary: str = ""
    tool_calls_made: int = 0
    duration_ms: int = 0
    success: bool = True


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool = True
    comment: str = ""


class ForeignKeyInfo(BaseModel):
    constrained_columns: list[str]
    referred_table: str
    referred_columns: list[str]


class TableSchema(BaseModel):
    name: str
    columns: list[ColumnInfo]
    primary_keys: list[str]
    foreign_keys: list[ForeignKeyInfo]
    comment: str = ""


class SchemaResponse(BaseModel):
    dialect: str
    table_count: int
    tables: list[TableSchema]


class SessionInfo(BaseModel):
    session_id: str
    dialect: str
    table_count: int
    tables: list[str]
    created_at: float


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_session_or_404(session_id: str) -> dict[str, Any]:
    if session_id not in _sessions:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found. Please reconnect.",
        )
    return _sessions[session_id]


# ── Global exception handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {exc}"},
    )


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    """Liveness probe."""
    return {"status": "ok", "version": "1.0.0", "service": "Wedy.ai Text2SQL API"}


# ── Sessions ──────────────────────────────────────────────────────────────────

@app.post("/api/sessions", response_model=ConnectResponse, tags=["Sessions"])
async def create_session(req: ConnectRequest):
    """
    Test the database connection, initialise a TextSQL engine, and return a
    ``session_id`` that must be passed to all subsequent endpoints.
    """
    # 1. Validate the connection string synchronously in a thread (SQLAlchemy blocks)
    try:
        db = await asyncio.to_thread(_test_and_inspect, req.connection_string)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Connection failed: {exc}")

    dialect: str = db["dialect"]
    tables: list[str] = db["tables"]

    # 2. Build the TextSQL engine
    engine = TextSQL(
        connection_string=req.connection_string,
        model=req.model,
        base_url=req.base_url,
        verify_ssl=req.verify_ssl,
        extra_body=req.extra_body,
        llm_api_key=req.llm_api_key,
        instructions=req.instructions,
    )

    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "engine": engine,
        "dialect": dialect,
        "tables": tables,
        "created_at": time.time(),
    }

    return ConnectResponse(
        session_id=session_id,
        dialect=dialect,
        table_count=len(tables),
        tables=tables,
        message=f"Connected to {dialect} database with {len(tables)} table(s).",
    )


def _test_and_inspect(connection_string: str) -> dict:
    """Blocking helper — runs in a thread pool."""
    db = Database(connection_string)
    if not db.test_connection():
        raise ValueError("Cannot reach the database. Check host, port, credentials.")
    schema = db.get_schema_summary()
    return {"dialect": db.dialect, "tables": list(schema.keys())}


@app.get("/api/sessions/{session_id}", response_model=SessionInfo, tags=["Sessions"])
def get_session(session_id: str):
    """Return metadata for an active session."""
    s = _get_session_or_404(session_id)
    return SessionInfo(
        session_id=session_id,
        dialect=s["dialect"],
        table_count=len(s["tables"]),
        tables=s["tables"],
        created_at=s["created_at"],
    )


@app.delete("/api/sessions/{session_id}", tags=["Sessions"])
def delete_session(session_id: str):
    """Terminate and remove a session."""
    _sessions.pop(session_id, None)
    return {"ok": True, "session_id": session_id}


# ── Schema ────────────────────────────────────────────────────────────────────

@app.get("/api/sessions/{session_id}/schema", response_model=SchemaResponse, tags=["Schema"])
async def get_schema(session_id: str):
    """Return the full schema of the connected database."""
    s = _get_session_or_404(session_id)
    engine: TextSQL = s["engine"]

    raw: dict = await asyncio.to_thread(engine.db.get_schema_summary)

    tables = [
        TableSchema(
            name=name,
            columns=[
                ColumnInfo(
                    name=col["name"],
                    type=col["type"],
                    nullable=col.get("nullable", True),
                    comment=col.get("comment") or "",
                )
                for col in info["columns"]
            ],
            primary_keys=info.get("primary_keys", []),
            foreign_keys=[
                ForeignKeyInfo(
                    constrained_columns=fk.get("constrained_columns", []),
                    referred_table=fk.get("referred_table", ""),
                    referred_columns=fk.get("referred_columns", []),
                )
                for fk in info.get("foreign_keys", [])
            ],
            comment=info.get("comment") or "",
        )
        for name, info in raw.items()
    ]

    return SchemaResponse(
        dialect=s["dialect"],
        table_count=len(tables),
        tables=tables,
    )


# ── Query endpoints ───────────────────────────────────────────────────────────

@app.post("/api/sessions/{session_id}/ask", response_model=QueryResponse, tags=["Query"])
async def ask(session_id: str, req: AskRequest):
    """
    **Agentic** text-to-SQL — the LLM explores the schema, writes SQL,
    executes it, and self-corrects until it produces a verified result.

    Slower but significantly more accurate on large or ambiguous schemas.
    """
    s = _get_session_or_404(session_id)
    engine: TextSQL = s["engine"]
    start = time.time()

    try:
        result = await asyncio.to_thread(engine.ask, req.question, req.max_rows)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return QueryResponse(
        question=result.question,
        sql=result.sql,
        data=result.data,
        error=result.error,
        commentary=result.commentary,
        tool_calls_made=result.tool_calls_made,
        duration_ms=int((time.time() - start) * 1000),
        success=result.success,
    )


@app.post("/api/sessions/{session_id}/write_sql", response_model=QueryResponse, tags=["Query"])
async def write_sql(session_id: str, req: WriteSQLRequest):
    """
    **Single-pass** SQL generation — dumps the schema into the prompt and asks
    the LLM to produce SQL in one call.

    Faster and cheaper than ``/ask``, but no self-correction.
    Best for small, well-documented schemas.
    """
    s = _get_session_or_404(session_id)
    engine: TextSQL = s["engine"]
    start = time.time()

    try:
        result = await asyncio.to_thread(
            engine.write_sql, req.question, req.execute, req.max_rows
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return QueryResponse(
        question=result.question,
        sql=result.sql,
        data=result.data,
        error=result.error,
        commentary=result.commentary,
        tool_calls_made=0,
        duration_ms=int((time.time() - start) * 1000),
        success=result.success,
    )
