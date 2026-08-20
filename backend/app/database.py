"""AgentForge's own persistence layer — separate from any database an Agent connects to.

This is SQLite for v1 via SQLAlchemy. Swapping to Postgres later is a DATABASE_URL
change, not a rewrite, because all access goes through the repository layer.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    """A file-based sqlite URL fails to connect if its parent directory doesn't exist yet
    (e.g. `./data/` on a fresh checkout) — create it up front so startup/scripts never
    depend on a developer having created it by hand."""
    if not database_url.startswith("sqlite:///"):
        return
    path = database_url.removeprefix("sqlite:///")
    if not path or path == ":memory:":
        return
    Path(path).resolve().parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_parent_dir(settings.database_url)

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_lightweight_migrations() -> None:
    """No Alembic yet (v1 — see database.py's own docstring), so new *additive* columns on
    *existing* tables are applied here idempotently. Base.metadata.create_all() only creates
    tables that don't exist yet — it never alters an existing table, so a fresh column added
    to a model is invisible to already-existing SQLite databases until this runs.

    Every migration here must be purely additive (ADD COLUMN with a safe default) — this is
    explicitly not a place for destructive changes. Existing rows must always end up with a
    safe, honest default, never silently lost or reinterpreted.
    """
    if not settings.database_url.startswith("sqlite"):
        return  # Only SQLite needs this; a real migration tool is required before Postgres.

    def _ensure_column(
        conn, table: str, column: str, ddl_type: str, default_sql: str | None, nullable: bool = False
    ) -> None:
        existing_columns = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()}
        if column in existing_columns:
            return
        constraint = "" if nullable else f" NOT NULL DEFAULT {default_sql}"
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}{constraint}"))
        conn.commit()

    with engine.connect() as conn:
        _ensure_column(conn, "knowledge_assets", "verified", "BOOLEAN", "0")
        _ensure_column(conn, "validation_tests", "expected_sql_verified", "BOOLEAN", "0")
        # Nullable: only populated for runs where a verified reference SQL was actually
        # executed — absent for expected_answer-only and exploratory runs, never a fake "0".
        _ensure_column(conn, "validation_runs", "reference_result", "TEXT", None, nullable=True)
        _ensure_column(conn, "validation_tests", "criteria", "TEXT", None, nullable=True)
        _ensure_column(conn, "validation_runs", "agent_answer", "TEXT", None, nullable=True)
        _ensure_column(conn, "validation_runs", "violated_requirement", "TEXT", None, nullable=True)
        _ensure_column(conn, "messages", "raw_answer", "TEXT", None, nullable=True)

        # Value rename, not new data: "user_created" -> "manual" (TEST_ORIGINS renamed for
        # clarity alongside adding "uploaded" as its own distinct origin). Idempotent — the
        # WHERE clause matches nothing once already applied.
        conn.execute(text("UPDATE validation_tests SET origin = 'manual' WHERE origin = 'user_created'"))
        conn.commit()
