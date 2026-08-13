from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_agent_or_404
from app.models.agent import Agent
from app.schemas.database_connection import (
    ConnectionCreateRequest,
    ConnectionSummaryOut,
    ConnectionTestRequest,
    ConnectionTestResponse,
)
from app.services import database_connection_service

router = APIRouter(prefix="/agents/{agent_id}/database", tags=["database-connections"])


@router.post("/test", response_model=ConnectionTestResponse)
def test_connection(
    payload: ConnectionTestRequest,
    agent: Agent = Depends(get_agent_or_404),
) -> ConnectionTestResponse:
    ok, error = database_connection_service.test_connection(payload)
    return ConnectionTestResponse(ok=ok, error=error)


@router.post("", response_model=ConnectionSummaryOut)
def create_connection(
    payload: ConnectionCreateRequest,
    agent: Agent = Depends(get_agent_or_404),
    db: Session = Depends(get_db),
) -> ConnectionSummaryOut:
    try:
        conn = database_connection_service.save_connection(db, agent, payload)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return conn


@router.put("", response_model=ConnectionSummaryOut)
def replace_connection(
    payload: ConnectionCreateRequest,
    agent: Agent = Depends(get_agent_or_404),
    db: Session = Depends(get_db),
) -> ConnectionSummaryOut:
    try:
        conn = database_connection_service.save_connection(db, agent, payload)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return conn


@router.get("", response_model=ConnectionSummaryOut)
def get_connection(
    agent: Agent = Depends(get_agent_or_404),
    db: Session = Depends(get_db),
) -> ConnectionSummaryOut:
    conn = database_connection_service.get_connection(db, agent.id)
    if not conn:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No database connected yet.")
    return conn


@router.post("/upload-sqlite")
async def upload_sqlite(
    file: UploadFile,
    agent: Agent = Depends(get_agent_or_404),
) -> dict:
    if not file.filename or not file.filename.lower().endswith((".db", ".sqlite", ".sqlite3")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Expected a .db/.sqlite/.sqlite3 file.")
    content = await file.read()
    path = database_connection_service.save_uploaded_sqlite(agent.id, file.filename, content)
    return {"sqlite_file_path": path, "original_filename": file.filename}
