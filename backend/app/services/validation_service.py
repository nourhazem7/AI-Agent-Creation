"""Validation Workspace — proving an agent actually understands its database before anyone
relies on it in Chat.

Every test run always calls the agent's *real* engine (text2sql_adapter.ask, via the exact
same resolve_engine_for_agent used by chat) — there is no second, parallel SQL-generation
path here. What differs per test is only how the result is judged, and the judgement is never
"does the agent's SQL/result match one reference SQL's result" — expected_sql is itself just
one LLM-generated candidate that can misinterpret a business question exactly like the agent
can, so comparing two independently-fallible interpretations byte-for-byte cannot produce a
trustworthy signal. Instead:

  - Technical failures (engine won't initialize, the AI model is unreachable, no SQL was
    produced, or the agent's own SQL errors) are deterministic and never reach a judge —
    status="error".
  - Every test that produced a real result is judged by
    text2sql_adapter.judge_business_answer(): does the agent's actual answer satisfy the
    business question, using the schema to understand the data. A verified expected_sql, when
    present, is executed for real and its result is shown as diagnostic evidence — never as
    ground truth the agent is compared against — see the judge's own docstring for why it's a
    two-stage call.

"SQL generated" is never treated as "test passed" on its own, and an expected_answer/criteria
is never invented — they only ever come from what the user (or the verified validation_suite
Knowledge Asset) actually supplied.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.integrations import text2sql_adapter
from app.models.agent import Agent
from app.models.validation_run import ValidationRun
from app.models.validation_test import ValidationTest
from app.repositories import knowledge_asset_repository, validation_repository
from app.services.chat_service import resolve_engine_for_agent
from app.services.database_connection_service import connection_string_for_agent

_MAX_RESULT_ROWS = 200


# ── Listing, with idempotent sync from the verified validation_suite asset ─────────────────


def _sync_from_knowledge_asset(db: Session, agent: Agent) -> None:
    """Mirror the ready+verified validation_suite Knowledge Asset's questions into
    ValidationTest rows, so the same 8 grounded questions built during Knowledge Assets show
    up here as ready-to-run tests. Idempotent: matched by (agent_id, question), so re-running
    this never creates duplicates and never touches tests the user has since edited."""
    asset = knowledge_asset_repository.get_by_agent_and_type(db, agent.id, "validation_suite")
    if not asset or asset.status != "ready" or not asset.verified or not asset.content:
        return

    try:
        candidates = json.loads(asset.content)
    except (json.JSONDecodeError, TypeError):
        return
    if not isinstance(candidates, list):
        return

    changed = False
    for item in candidates:
        if not isinstance(item, dict):
            continue
        question = (item.get("question") or "").strip()
        if not question or validation_repository.get_by_question(db, agent.id, question):
            continue
        validation_repository.create_test(
            db,
            agent_id=agent.id,
            question=question,
            expected_sql=item.get("expected_sql") or None,
            expected_answer=item.get("expected_answer") or None,
            origin="ai_generated",
            expected_sql_verified=bool(item.get("sql_verified")),
        )
        changed = True

    if changed:
        db.commit()


def list_tests(db: Session, agent: Agent) -> list[ValidationTest]:
    _sync_from_knowledge_asset(db, agent)
    return validation_repository.list_tests_by_agent(db, agent.id)


def get_summary(db: Session, agent: Agent) -> dict:
    tests = list_tests(db, agent)
    counts = {"total": len(tests), "passed": 0, "partial": 0, "failed": 0, "error": 0, "inconclusive": 0, "not_run": 0}
    for test in tests:
        counts[test.last_status] = counts.get(test.last_status, 0) + 1
    return counts


def _maybe_advance_to_validated(db: Session, agent: Agent) -> None:
    """Called after every judged run. The one real, non-arbitrary signal that validation has
    actually succeeded: every test the agent has has been run and judged "passed" — the same
    "no outstanding issues" condition the Validate page's own UI already uses. Forward-only —
    never regresses an agent that's already validated/active because a later-added test hasn't
    been run yet."""
    if agent.status in ("validated", "active"):
        return
    summary = get_summary(db, agent)
    if summary["total"] > 0 and summary["passed"] == summary["total"]:
        agent.status = "validated"


# ── Creating user-authored tests ────────────────────────────────────────────────────────────


def create_user_test(
    db: Session,
    agent: Agent,
    *,
    question: str,
    expected_sql: str | None = None,
    expected_answer: str | None = None,
    criteria: str | None = None,
    notes: str | None = None,
) -> ValidationTest:
    """A non-technical user is never required to supply SQL. When they (optionally) do supply
    expected_sql, it's executed against the real database right now — a broken/unrunnable
    expected_sql is never silently stored as if it were trustworthy reference data. `criteria`
    is the one field treated as authoritative by the judge (see validation_service module
    docstring) — a human's own statement of hard requirements, never LLM-generated."""
    expected_sql = expected_sql.strip() if expected_sql and expected_sql.strip() else None
    expected_answer = expected_answer.strip() if expected_answer and expected_answer.strip() else None
    criteria = criteria.strip() if criteria and criteria.strip() else None

    verified = False
    if expected_sql:
        conn_str = connection_string_for_agent(db, agent)
        ok, error = text2sql_adapter.validate_sql_against_db(conn_str, expected_sql)
        if not ok:
            raise ValueError(f"expected_sql does not run against this agent's database: {error}")
        verified = True

    test = validation_repository.create_test(
        db,
        agent_id=agent.id,
        question=question.strip(),
        expected_sql=expected_sql,
        expected_answer=expected_answer,
        criteria=criteria,
        notes=notes.strip() if notes and notes.strip() else None,
        origin="user_created",
        expected_sql_verified=verified,
    )
    db.commit()
    db.refresh(test)
    return test


def delete_test(db: Session, test: ValidationTest) -> None:
    validation_repository.delete_test(db, test)
    db.commit()


# ── Running tests ────────────────────────────────────────────────────────────────────────────


def run_test(db: Session, agent: Agent, test: ValidationTest) -> ValidationRun:
    try:
        engine = resolve_engine_for_agent(db, agent)
    except ValueError as exc:
        run = validation_repository.add_run(
            db,
            validation_test_id=test.id,
            agent_id=agent.id,
            status="error",
            error_message=str(exc),
            comparison_note="Could not run: the agent's reasoning engine failed to initialize.",
        )
        test.last_status = "error"
        db.commit()
        db.refresh(run)
        return run

    try:
        result = text2sql_adapter.ask(engine, test.question, max_rows=_MAX_RESULT_ROWS)
    except Exception as exc:  # noqa: BLE001 - LLM/network failure, never let it 500 the run
        run = validation_repository.add_run(
            db,
            validation_test_id=test.id,
            agent_id=agent.id,
            status="error",
            error_message=f"Could not reach the AI model: {exc}",
            comparison_note="Could not run: the AI model was unreachable.",
        )
        test.last_status = "error"
        db.commit()
        db.refresh(run)
        return run

    result_json = json.dumps(result.data[:_MAX_RESULT_ROWS], default=str) if result.data else None

    if result.error or not result.sql:
        run = validation_repository.add_run(
            db,
            validation_test_id=test.id,
            agent_id=agent.id,
            status="error",
            generated_sql=result.sql or None,
            result_data=result_json,
            error_message=result.error or "The model did not produce a usable answer.",
            comparison_note="Could not run: the agent failed to produce SQL for this question.",
            input_tokens=result.input_tokens or None,
            output_tokens=result.output_tokens or None,
            iterations=result.iterations or None,
        )
        test.last_status = "error"
        db.commit()
        db.refresh(run)
        return run

    # A real result exists — hand it to the business-answer judge. A verified reference SQL,
    # when present, is executed for real (for display + as secondary diagnostic evidence inside
    # the judge) but its own execution failure never counts against the agent.
    conn_str = connection_string_for_agent(db, agent)
    schema_summary = text2sql_adapter.introspect_schema(conn_str)

    reference_result_json: str | None = None
    reference_rows: list[dict] | None = None
    if test.expected_sql and test.expected_sql_verified:
        rows, ref_error = text2sql_adapter.get_reference_result(conn_str, test.expected_sql)
        if rows is not None:
            reference_rows = rows
            reference_result_json = json.dumps(rows[:_MAX_RESULT_ROWS], default=str)
        # ref_error is intentionally not surfaced as an agent-facing error — a broken reference
        # solution just means the judge proceeds without it (see judge_business_answer).

    verdict = text2sql_adapter.judge_business_answer(
        agent.llm_model,
        question=test.question,
        schema_summary=schema_summary,
        agent_sql=result.sql,
        agent_commentary=result.commentary or "",
        agent_rows=result.data or [],
        criteria=test.criteria,
        expected_answer=test.expected_answer,
        reference_sql=test.expected_sql if test.expected_sql_verified else None,
        reference_rows=reference_rows,
    )

    run = validation_repository.add_run(
        db,
        validation_test_id=test.id,
        agent_id=agent.id,
        status=verdict["verdict"],
        generated_sql=result.sql,
        result_data=result_json,
        agent_answer=result.commentary or None,
        reference_result=reference_result_json,
        comparison_note=verdict["reasoning"],
        violated_requirement=verdict["violated_requirement"],
        input_tokens=result.input_tokens or None,
        output_tokens=result.output_tokens or None,
        iterations=result.iterations or None,
    )
    test.last_status = verdict["verdict"]
    _maybe_advance_to_validated(db, agent)
    db.commit()
    db.refresh(run)
    return run


def run_all(db: Session, agent: Agent) -> list[ValidationRun]:
    tests = list_tests(db, agent)
    return [run_test(db, agent, test) for test in tests]


def run_failed(db: Session, agent: Agent) -> list[ValidationRun]:
    tests = [
        t for t in list_tests(db, agent)
        if t.last_status in ("failed", "error", "partial", "inconclusive")
    ]
    return [run_test(db, agent, test) for test in tests]
