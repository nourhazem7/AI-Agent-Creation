"""AgentForge's own persistence layer — separate from any database an Agent connects to.

This is SQLite for v1 via SQLAlchemy. Swapping to Postgres later is a DATABASE_URL
change, not a rewrite, because all access goes through the repository layer.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
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
