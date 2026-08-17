"""Chat orchestration — the actual 'user question -> answer' path.

Flow: user question -> this service -> current agent's cached TextSQL engine (via the
adapter) -> text2sql's own schema exploration / SQL generation -> the company LLM endpoint
-> generated SQL -> the agent's real database -> result -> a Message the frontend can render
(natural-language answer + optional SQL + optional result table).

Every failure category is caught here and turned into either a clean precondition error
(agent/conversation not found, no database connected — raised as ValueError, mapped to an
HTTP 4xx by the router) or a normal assistant Message with error_message set (LLM
unreachable, SQL execution failure, empty/invalid response) — the conversation keeps
flowing like a real chat product instead of the request just blowing up.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrations import text2sql_adapter
from app.models.agent import Agent
from app.models.conversation import Conversation
from app.models.message import Message
from app.repositories import conversation_repository, knowledge_asset_repository, message_repository
from app.services.database_connection_service import connection_string_for_agent

settings = get_settings()

_MAX_RESULT_ROWS = 200


def list_conversations(db: Session, agent_id: str) -> list[Conversation]:
    return conversation_repository.list_by_agent(db, agent_id)


def create_conversation(db: Session, agent_id: str, user_id: str) -> Conversation:
    conversation = conversation_repository.create(db, agent_id=agent_id, user_id=user_id)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_conversation(db: Session, conversation_id: str) -> Conversation | None:
    return conversation_repository.get(db, conversation_id)


def delete_conversation(db: Session, conversation: Conversation) -> None:
    conversation_repository.delete(db, conversation)
    db.commit()


def list_messages(db: Session, conversation_id: str) -> list[Message]:
    return message_repository.list_by_conversation(db, conversation_id)


def resolve_engine_for_agent(db: Session, agent: Agent):
    """Build (or reuse the cached) TextSQL engine for this exact agent. Raises ValueError
    for any setup-level problem — no database connected, or the engine itself fails to
    initialize (bad config, unreachable DB at construction time, etc.).

    Public so other services (e.g. validation_service) can reuse the exact same
    engine-construction path instead of duplicating it."""
    connection_string = connection_string_for_agent(db, agent)  # raises ValueError if unset

    doc_asset = knowledge_asset_repository.get_by_agent_and_type(db, agent.id, "documentation")
    metadata_hint = doc_asset.content if doc_asset and doc_asset.status == "ready" else None

    trace_dir = Path(settings.storage_dir) / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_file = str(trace_dir / f"{agent.id}.jsonl")

    try:
        return text2sql_adapter.get_engine(
            agent_id=agent.id,
            knowledge_version=agent.knowledge_version,
            llm_model=agent.llm_model,
            connection_string=connection_string,
            custom_instructions=agent.custom_instructions,
            metadata_hint=metadata_hint,
            trace_file=trace_file,
        )
    except Exception as exc:  # noqa: BLE001 - a bad config must surface clearly, not 500 blindly
        raise ValueError(f"Could not initialize this agent's reasoning engine: {exc}") from exc


def _result_data_json(rows: list[dict]) -> str:
    return json.dumps(rows[:_MAX_RESULT_ROWS], default=str)


def _store_error_reply(db: Session, conversation: Conversation, error_text: str, sql: str | None = None) -> Message:
    message = message_repository.create(
        db,
        conversation_id=conversation.id,
        role="assistant",
        content="I ran into a problem answering that question.",
        sql=sql,
        error_message=error_text,
    )
    db.commit()
    db.refresh(message)
    return message


def _store_success_reply(db: Session, conversation: Conversation, result) -> Message:
    content = result.commentary.strip() if result.commentary else "Here's what I found."
    message = message_repository.create(
        db,
        conversation_id=conversation.id,
        role="assistant",
        content=content,
        sql=result.sql,
        result_data=_result_data_json(result.data) if result.data else None,
        response_type="table" if result.data else "text",
        input_tokens=result.input_tokens or None,
        output_tokens=result.output_tokens or None,
    )
    if conversation.title == "New chat":
        conversation.title = result.question[:60]
    db.commit()
    db.refresh(message)
    return message


def send_message(db: Session, agent: Agent, conversation: Conversation, question: str) -> Message:
    """The synchronous ask() path. Always returns a Message (the assistant's reply) — never
    raises for mid-conversation failures (LLM unreachable, SQL execution failure, empty
    response); those become an error-flagged assistant Message so the chat degrades
    gracefully instead of the HTTP request failing outright."""
    message_repository.create(db, conversation_id=conversation.id, role="user", content=question)
    db.commit()

    try:
        engine = resolve_engine_for_agent(db, agent)
    except ValueError as exc:
        return _store_error_reply(db, conversation, str(exc))

    try:
        result = text2sql_adapter.ask(engine, question, max_rows=_MAX_RESULT_ROWS)
    except Exception as exc:  # noqa: BLE001 - network/LLM failure mid-conversation
        return _store_error_reply(db, conversation, f"Could not reach the AI model: {exc}")

    if result.error or not result.sql:
        return _store_error_reply(
            db, conversation, result.error or "The model did not produce a usable answer.", sql=result.sql or None
        )

    return _store_success_reply(db, conversation, result)


def stream_message(db: Session, agent: Agent, conversation: Conversation, question: str) -> Iterator[dict]:
    """The streaming path — same guarantees as send_message, but yields progress events
    (safe high-level labels only, e.g. "Exploring database schema" — no chain-of-thought)
    as the agent works, then a final event with the stored Message."""
    message_repository.create(db, conversation_id=conversation.id, role="user", content=question)
    db.commit()

    try:
        engine = resolve_engine_for_agent(db, agent)
    except ValueError as exc:
        error_message = _store_error_reply(db, conversation, str(exc))
        yield {"type": "error", "error": str(exc), "message_id": error_message.id}
        return

    try:
        for kind, payload in text2sql_adapter.stream_ask(engine, question, max_rows=_MAX_RESULT_ROWS):
            if kind == "step":
                yield {"type": "progress", "label": payload.get("label", "Working...")}
            elif kind == "result":
                result = payload
                if result.error or not result.sql:
                    error_message = _store_error_reply(
                        db,
                        conversation,
                        result.error or "The model did not produce a usable answer.",
                        sql=result.sql or None,
                    )
                    yield {"type": "error", "error": error_message.error_message, "message_id": error_message.id}
                else:
                    message = _store_success_reply(db, conversation, result)
                    yield {
                        "type": "result",
                        "message_id": message.id,
                        "content": message.content,
                        "sql": message.sql,
                        "response_type": message.response_type,
                    }
    except Exception as exc:  # noqa: BLE001 - network/LLM failure mid-stream
        error_message = _store_error_reply(db, conversation, f"Could not reach the AI model: {exc}")
        yield {"type": "error", "error": error_message.error_message, "message_id": error_message.id}
