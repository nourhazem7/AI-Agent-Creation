from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_agent_or_404, get_conversation_or_404, get_current_user
from app.models.agent import Agent
from app.models.conversation import Conversation
from app.models.user import User
from app.schemas.chat import ConversationOut, MessageCreateRequest, MessageOut
from app.services import chat_service

router = APIRouter(tags=["chat"])


@router.get("/agents/{agent_id}/conversations", response_model=list[ConversationOut])
def list_conversations(agent: Agent = Depends(get_agent_or_404), db: Session = Depends(get_db)) -> list:
    return chat_service.list_conversations(db, agent.id)


@router.post("/agents/{agent_id}/conversations", response_model=ConversationOut)
def create_conversation(
    agent: Agent = Depends(get_agent_or_404),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Conversation:
    return chat_service.create_conversation(db, agent.id, current_user.id)


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation: Conversation = Depends(get_conversation_or_404), db: Session = Depends(get_db)
) -> dict:
    chat_service.delete_conversation(db, conversation)
    return {"ok": True}


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(
    conversation: Conversation = Depends(get_conversation_or_404), db: Session = Depends(get_db)
) -> list:
    return chat_service.list_messages(db, conversation.id)


@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut)
def send_message(
    payload: MessageCreateRequest,
    conversation: Conversation = Depends(get_conversation_or_404),
    db: Session = Depends(get_db),
):
    agent = db.get(Agent, conversation.agent_id)
    return chat_service.send_message(db, agent, conversation, payload.question)


@router.post("/conversations/{conversation_id}/messages/stream")
def stream_message(
    payload: MessageCreateRequest,
    conversation: Conversation = Depends(get_conversation_or_404),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Server-Sent Events: a stream of {"type": "progress"|"result"|"error", ...} JSON lines
    as the agent explores the schema and writes SQL, ending with the stored message. Progress
    labels are safe/high-level only (e.g. "Exploring database schema") — no chain-of-thought."""
    agent = db.get(Agent, conversation.agent_id)

    def event_stream():
        for event in chat_service.stream_message(db, agent, conversation, payload.question):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
