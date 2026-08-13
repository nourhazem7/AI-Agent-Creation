from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.database_connection import DatabaseConnection


def get_by_agent(db: Session, agent_id: str) -> DatabaseConnection | None:
    stmt = select(DatabaseConnection).where(DatabaseConnection.agent_id == agent_id)
    return db.execute(stmt).scalar_one_or_none()


def upsert(
    db: Session,
    *,
    agent_id: str,
    dialect: str,
    host: str | None,
    port: int | None,
    database_name: str | None,
    username: str | None,
    encrypted_password: str | None,
    sqlite_file_path: str | None,
) -> DatabaseConnection:
    conn = get_by_agent(db, agent_id)
    if conn is None:
        conn = DatabaseConnection(agent_id=agent_id)
        db.add(conn)

    conn.dialect = dialect
    conn.host = host
    conn.port = port
    conn.database_name = database_name
    conn.username = username
    conn.encrypted_password = encrypted_password
    conn.sqlite_file_path = sqlite_file_path

    db.flush()
    return conn
