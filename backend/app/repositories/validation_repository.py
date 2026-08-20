from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.validation_run import ValidationRun
from app.models.validation_test import ValidationTest


def list_tests_by_agent(db: Session, agent_id: str) -> list[ValidationTest]:
    stmt = (
        select(ValidationTest)
        .where(ValidationTest.agent_id == agent_id)
        .order_by(ValidationTest.created_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


def get_test(db: Session, test_id: str) -> ValidationTest | None:
    return db.get(ValidationTest, test_id)


def get_test_for_agent(db: Session, agent_id: str, test_id: str) -> ValidationTest | None:
    """Agent-scoped lookup — a test_id belonging to a different agent must never resolve."""
    test = db.get(ValidationTest, test_id)
    if test is None or test.agent_id != agent_id:
        return None
    return test


def get_by_question(db: Session, agent_id: str, question: str) -> ValidationTest | None:
    """Existence check only (used to skip re-inserting a question the sync already created) —
    deliberately tolerant of more than one match rather than asserting uniqueness, since
    (agent_id, question) has no DB-level uniqueness constraint and older data may already have
    duplicates."""
    stmt = (
        select(ValidationTest)
        .where(ValidationTest.agent_id == agent_id, ValidationTest.question == question)
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def create_test(
    db: Session,
    *,
    agent_id: str,
    question: str,
    expected_sql: str | None = None,
    expected_answer: str | None = None,
    criteria: str | None = None,
    notes: str | None = None,
    origin: str = "manual",
    expected_sql_verified: bool = False,
) -> ValidationTest:
    test = ValidationTest(
        agent_id=agent_id,
        question=question,
        expected_sql=expected_sql,
        expected_answer=expected_answer,
        criteria=criteria,
        notes=notes,
        origin=origin,
        expected_sql_verified=expected_sql_verified,
    )
    db.add(test)
    db.flush()
    return test


def delete_test(db: Session, test: ValidationTest) -> None:
    db.delete(test)


def add_run(
    db: Session,
    *,
    validation_test_id: str,
    agent_id: str,
    status: str,
    generated_sql: str | None = None,
    result_data: str | None = None,
    agent_answer: str | None = None,
    reference_result: str | None = None,
    error_message: str | None = None,
    comparison_note: str | None = None,
    violated_requirement: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    iterations: int | None = None,
) -> ValidationRun:
    run = ValidationRun(
        validation_test_id=validation_test_id,
        agent_id=agent_id,
        status=status,
        generated_sql=generated_sql,
        result_data=result_data,
        agent_answer=agent_answer,
        reference_result=reference_result,
        error_message=error_message,
        comparison_note=comparison_note,
        violated_requirement=violated_requirement,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        iterations=iterations,
    )
    db.add(run)
    db.flush()
    return run


def latest_run(db: Session, test_id: str) -> ValidationRun | None:
    stmt = (
        select(ValidationRun)
        .where(ValidationRun.validation_test_id == test_id)
        .order_by(ValidationRun.created_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def list_runs_for_test(db: Session, test_id: str) -> list[ValidationRun]:
    stmt = (
        select(ValidationRun)
        .where(ValidationRun.validation_test_id == test_id)
        .order_by(ValidationRun.created_at.asc())
    )
    return list(db.execute(stmt).scalars().all())
