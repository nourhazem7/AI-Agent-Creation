from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrations import text2sql_adapter
from app.models.agent import Agent
from app.models.common import utcnow
from app.models.database_connection import DatabaseConnection
from app.repositories import database_connection_repository
from app.schemas.database_connection import ConnectionFields
from app.security import decrypt_secret, encrypt_secret

settings = get_settings()


def test_connection(payload: ConnectionFields) -> tuple[bool, str | None]:
    conn_str = text2sql_adapter.build_connection_string(
        dialect=payload.dialect,
        host=payload.host,
        port=payload.port,
        database_name=payload.database_name,
        username=payload.username,
        password=payload.password,
        sqlite_file_path=payload.sqlite_file_path,
    )
    return text2sql_adapter.test_connection(conn_str)


def get_connection(db: Session, agent_id: str) -> DatabaseConnection | None:
    return database_connection_repository.get_by_agent(db, agent_id)


def save_connection(db: Session, agent: Agent, payload: ConnectionFields) -> DatabaseConnection:
    """Test the connection, then persist it (password encrypted). Raises ValueError if
    the connection doesn't actually work — we never save a connection we haven't verified."""
    ok, error = test_connection(payload)
    if not ok:
        raise ValueError(error or "Could not connect to the database.")

    conn = database_connection_repository.upsert(
        db,
        agent_id=agent.id,
        dialect=payload.dialect,
        host=payload.host,
        port=payload.port,
        database_name=payload.database_name,
        username=payload.username,
        encrypted_password=encrypt_secret(payload.password) if payload.password else None,
        sqlite_file_path=payload.sqlite_file_path,
    )
    conn.is_connected = True
    conn.last_tested_at = utcnow()

    if agent.status in ("draft", "connecting", "error"):
        agent.status = "configuring_knowledge"
    agent.knowledge_version += 1

    db.commit()
    db.refresh(conn)
    # New knowledge_version means the old cache key is orphaned anyway, but evict it
    # explicitly so a stale engine (old connection) never lingers in memory.
    text2sql_adapter.invalidate_engine(agent.id)
    return conn


def decrypted_password(conn: DatabaseConnection) -> str | None:
    if not conn.encrypted_password:
        return None
    return decrypt_secret(conn.encrypted_password)


def connection_string_for_agent(db: Session, agent: Agent) -> str:
    """Resolve an agent's live connection string. Raises ValueError if no database is
    connected yet — the standard precondition error every caller (knowledge assets, chat)
    surfaces the same way."""
    conn = database_connection_repository.get_by_agent(db, agent.id)
    if not conn:
        raise ValueError("Connect a database before chatting with this agent.")
    return text2sql_adapter.connection_string_for(conn, decrypted_password(conn))


def save_uploaded_sqlite(agent_id: str, filename: str, content: bytes) -> str:
    """Save an uploaded .db/.sqlite file under storage/uploads/{agent_id}/database/ and
    return its path (used as sqlite_file_path when creating the connection)."""
    safe_name = Path(filename).name  # strip any directory components
    target_dir = Path(settings.storage_dir) / "uploads" / agent_id / "database"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / safe_name
    target_path.write_bytes(content)
    return str(target_path.resolve())
