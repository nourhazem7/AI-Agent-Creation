"""Validation Workspace — proving an agent actually understands its database before anyone
relies on it in Chat.

Every test run always calls the agent's *real* engine (text2sql_adapter.ask, via the exact
same resolve_engine_for_agent used by chat) — there is no second, parallel SQL-generation
path here. What differs per test is only how the result is judged, and that judgement
follows one of three branches, decided per-test from what the test actually has:

  1. A verified expected_sql is set -> the authoritative branch. Both the agent's own SQL and
                                        the reference SQL are executed for real, right now, and
                                        their *row values* are compared (order-independent) —
                                        not just "SQL was produced". The reference result is
                                        persisted on the run so the UI can show it directly,
                                        rather than asking the reader to trust a verdict.
  2. Otherwise, expected_answer is set -> loose containment check against the generated
                                        answer/rows. This is a heuristic fallback used only
                                        when there's no verified SQL to check against
                                        deterministically — for AI-generated tests this field
                                        is often a *description* of the expected result shape,
                                        not a literal value, so it is never treated as more
                                        authoritative than a verified reference SQL.
  3. Neither is set                  -> exploratory: passed only if the engine produced SQL and
                                        no error. This is never conflated with "the answer is
                                        correct" — the comparison_note says so every time.

"SQL generated" is never treated as "test passed" on its own outside branch 3, and an
expected_answer is never invented — it only ever comes from what the user (or the verified
validation_suite Knowledge Asset) actually supplied.
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
    counts = {"total": len(tests), "passed": 0, "failed": 0, "error": 0, "not_run": 0}
    for test in tests:
        counts[test.last_status] = counts.get(test.last_status, 0) + 1
    return counts


# ── Creating user-authored tests ────────────────────────────────────────────────────────────


def create_user_test(
    db: Session,
    agent: Agent,
    *,
    question: str,
    expected_sql: str | None = None,
    expected_answer: str | None = None,
    notes: str | None = None,
) -> ValidationTest:
    """A non-technical user is never required to supply SQL. When they (optionally) do supply
    expected_sql, it's executed against the real database right now — a broken/unrunnable
    expected_sql is never silently stored as if it were trustworthy reference data."""
    expected_sql = expected_sql.strip() if expected_sql and expected_sql.strip() else None
    expected_answer = expected_answer.strip() if expected_answer and expected_answer.strip() else None

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


def _rows_match(actual: list[dict], reference: list[dict]) -> bool:
    """Order-independent comparison of two row sets by value. Compares by column *position*
    (dict insertion order == SELECT order), never by column name/alias — the agent's own SQL
    and a user's hand-written reference SQL routinely select the same data under different
    aliases (e.g. `total_orders` vs `order_count`), and that must not count as a mismatch.
    Cell values are stringified first so int/float/str representation differences between the
    two SQL executions don't produce false negatives either."""
    if len(actual) != len(reference):
        return False
    if actual and reference and len(actual[0]) != len(reference[0]):
        return False

    def _normalize(rows: list[dict]) -> list[tuple]:
        return sorted(tuple("" if v is None else str(v) for v in row.values()) for row in rows)

    return _normalize(actual) == _normalize(reference)


def _answer_contains(generated_answer: str, generated_rows: list[dict], expected_answer: str) -> bool:
    """Loose containment check: the expected answer text must show up, case-insensitively,
    either in the model's natural-language commentary or in the stringified row data. This is
    explicitly a heuristic, never claimed as exact semantic matching — comparison_note says so."""
    needle = expected_answer.strip().lower()
    if not needle:
        return False
    if needle in generated_answer.lower():
        return True
    haystack = json.dumps(generated_rows, default=str).lower()
    return needle in haystack


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

    reference_result_json: str | None = None

    # Branch 1: a verified reference SQL exists — the authoritative, deterministic check.
    # Takes priority over expected_answer even when both are set, because expected_answer
    # (especially for AI-generated tests) is frequently a *description* of the expected
    # result, not a literal value, and must never outrank an actual database comparison.
    if test.expected_sql and test.expected_sql_verified:
        try:
            conn_str = connection_string_for_agent(db, agent)
            reference_rows, ref_error = text2sql_adapter.get_reference_result(conn_str, test.expected_sql)
        except ValueError as exc:
            reference_rows, ref_error = None, str(exc)

        if ref_error or reference_rows is None:
            status = "error"
            note = f"Could not run: the reference expected_sql failed to execute ({ref_error})."
        else:
            reference_result_json = json.dumps(reference_rows[:_MAX_RESULT_ROWS], default=str)
            matched = _rows_match(result.data or [], reference_rows)
            status = "passed" if matched else "failed"
            note = (
                "Compared the agent's own generated SQL's results against the verified reference "
                f"SQL's actual results (order-independent row comparison). "
                f"{'Rows matched.' if matched else 'Rows did not match.'}"
            )

    # Branch 2: expected_answer given, with no verified reference SQL to check against
    # deterministically — a looser, explicitly-labeled heuristic fallback.
    elif test.expected_answer:
        matched = _answer_contains(result.commentary or "", result.data or [], test.expected_answer)
        status = "passed" if matched else "failed"
        note = (
            f"No verified reference SQL was available, so this was compared against the "
            f"expected-answer text using a loose, case-insensitive containment check (not exact "
            f"semantic matching). "
            f"{'Found' if matched else 'Did not find'} \"{test.expected_answer}\" in the agent's "
            f"response."
        )

    # Branch 3: exploratory — no expectation was ever supplied, so "passed" only means the
    # agent produced runnable SQL and no error. This is never described as a correctness check.
    else:
        status = "passed"
        note = (
            "Exploratory test — no expected answer or reference SQL was supplied, so this only "
            "confirms the agent produced SQL and ran it without error. It does not verify the "
            "answer is correct."
        )

    run = validation_repository.add_run(
        db,
        validation_test_id=test.id,
        agent_id=agent.id,
        status=status,
        generated_sql=result.sql,
        result_data=result_json,
        reference_result=reference_result_json,
        comparison_note=note,
        input_tokens=result.input_tokens or None,
        output_tokens=result.output_tokens or None,
        iterations=result.iterations or None,
    )
    test.last_status = status
    db.commit()
    db.refresh(run)
    return run


def run_all(db: Session, agent: Agent) -> list[ValidationRun]:
    tests = list_tests(db, agent)
    return [run_test(db, agent, test) for test in tests]


def run_failed(db: Session, agent: Agent) -> list[ValidationRun]:
    tests = [t for t in list_tests(db, agent) if t.last_status in ("failed", "error")]
    return [run_test(db, agent, test) for test in tests]
