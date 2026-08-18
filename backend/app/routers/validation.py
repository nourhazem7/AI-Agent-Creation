from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_agent_or_404, get_agent_owner_or_404
from app.models.agent import Agent
from app.repositories import validation_repository
from app.schemas.validation import RunSummary, ValidationRunOut, ValidationTestCreate, ValidationTestOut
from app.services import validation_service

router = APIRouter(tags=["validation"])


def _to_out(db: Session, test) -> ValidationTestOut:
    out = ValidationTestOut.model_validate(test)
    run = validation_repository.latest_run(db, test.id)
    out.latest_run = ValidationRunOut.model_validate(run) if run else None
    return out


def _get_test_or_404(db: Session, agent: Agent, test_id: str):
    test = validation_repository.get_test_for_agent(db, agent.id, test_id)
    if not test:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Validation test not found")
    return test


@router.get("/agents/{agent_id}/validation-tests", response_model=list[ValidationTestOut])
def list_tests(agent: Agent = Depends(get_agent_or_404), db: Session = Depends(get_db)) -> list[ValidationTestOut]:
    tests = validation_service.list_tests(db, agent)
    return [_to_out(db, t) for t in tests]


@router.get("/agents/{agent_id}/validation-summary", response_model=RunSummary)
def get_summary(agent: Agent = Depends(get_agent_or_404), db: Session = Depends(get_db)) -> dict:
    return validation_service.get_summary(db, agent)


@router.post("/agents/{agent_id}/validation-tests", response_model=ValidationTestOut)
def create_test(
    payload: ValidationTestCreate,
    agent: Agent = Depends(get_agent_owner_or_404),
    db: Session = Depends(get_db),
) -> ValidationTestOut:
    try:
        test = validation_service.create_user_test(
            db,
            agent,
            question=payload.question,
            expected_sql=payload.expected_sql,
            expected_answer=payload.expected_answer,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return _to_out(db, test)


@router.delete("/agents/{agent_id}/validation-tests/{test_id}")
def delete_test(
    test_id: str,
    agent: Agent = Depends(get_agent_owner_or_404),
    db: Session = Depends(get_db),
) -> dict:
    test = _get_test_or_404(db, agent, test_id)
    validation_service.delete_test(db, test)
    return {"ok": True}


@router.post("/agents/{agent_id}/validation-tests/{test_id}/run", response_model=ValidationTestOut)
def run_test(
    test_id: str,
    agent: Agent = Depends(get_agent_owner_or_404),
    db: Session = Depends(get_db),
) -> ValidationTestOut:
    test = _get_test_or_404(db, agent, test_id)
    validation_service.run_test(db, agent, test)
    db.refresh(test)
    return _to_out(db, test)


@router.post("/agents/{agent_id}/validation-tests/run-all", response_model=list[ValidationTestOut])
def run_all(agent: Agent = Depends(get_agent_owner_or_404), db: Session = Depends(get_db)) -> list[ValidationTestOut]:
    validation_service.run_all(db, agent)
    tests = validation_repository.list_tests_by_agent(db, agent.id)
    return [_to_out(db, t) for t in tests]


@router.post("/agents/{agent_id}/validation-tests/run-failed", response_model=list[ValidationTestOut])
def run_failed(agent: Agent = Depends(get_agent_owner_or_404), db: Session = Depends(get_db)) -> list[ValidationTestOut]:
    validation_service.run_failed(db, agent)
    tests = validation_repository.list_tests_by_agent(db, agent.id)
    return [_to_out(db, t) for t in tests]
