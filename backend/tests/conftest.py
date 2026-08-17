from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet

# Must happen before any `app.*` import — Settings/engine are built at import time.
_TEST_DB_PATH = Path(__file__).resolve().parent / "test_agentforge.db"
if _TEST_DB_PATH.exists():
    _TEST_DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH.as_posix()}"
os.environ["FERNET_KEY"] = Fernet.generate_key().decode()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.models  # noqa: E402,F401 - register every model before create_all()
from app.database import Base, engine, get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.repositories.agent_repository import create_agent  # noqa: E402
from app.repositories.company_repository import create_company  # noqa: E402
from app.repositories.user_repository import create_user  # noqa: E402
from app.security import hash_password  # noqa: E402


# pysqlite manages its own implicit transactions in a way that fights explicit
# connection.begin()/begin_nested() unless disabled like this — the documented recipe for
# SAVEPOINT-based test isolation with SQLite. See:
# https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#serializable-isolation-savepoints-transactional-ddl
@event.listens_for(engine, "connect")
def _sqlite_disable_pysqlite_txn(dbapi_connection, _record):
    dbapi_connection.isolation_level = None


@event.listens_for(engine, "begin")
def _sqlite_emit_begin(conn):
    conn.exec_driver_sql("BEGIN")


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()
    if _TEST_DB_PATH.exists():
        _TEST_DB_PATH.unlink()


@pytest.fixture()
def db() -> Session:
    """Each test runs inside an outer transaction + SAVEPOINT so the service-layer's
    internal `db.commit()` calls never leak data between tests — the outer transaction
    is rolled back unconditionally at teardown."""
    connection = engine.connect()
    outer_txn = connection.begin()
    session = Session(bind=connection)
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            sess.expire_all()
            sess.begin_nested()

    try:
        yield session
    finally:
        session.close()
        outer_txn.rollback()
        connection.close()


@pytest.fixture()
def client(db: Session) -> TestClient:
    def _override_get_db():
        yield db

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def scenario(db: Session):
    """Company A: admin, owner (owns `agent`), a user later made editor, a user later
    made viewer, an unrelated member with no access, and an inactive member.
    Company B: one user, for cross-company negative tests.
    """
    company_a = create_company(db, name="Company A")
    company_b = create_company(db, name="Company B")

    def _user(company_id: str, email: str, name: str, role: str = "member"):
        return create_user(
            db,
            company_id=company_id,
            email=email,
            hashed_password=hash_password("dev-only-not-a-real-password"),
            full_name=name,
            role=role,
        )

    admin = _user(company_a.id, "admin@company-a.test", "Admin A", role="admin")
    owner = _user(company_a.id, "owner@company-a.test", "Owner A")
    editor_target = _user(company_a.id, "editor@company-a.test", "Editor A")
    viewer_target = _user(company_a.id, "viewer@company-a.test", "Viewer A")
    outsider = _user(company_a.id, "outsider@company-a.test", "Outsider A")
    inactive = _user(company_a.id, "inactive@company-a.test", "Inactive A")
    inactive.is_active = False
    company_b_user = _user(company_b.id, "user@company-b.test", "User B", role="admin")

    # This scenario is about role/permission behavior on an otherwise-normal agent, so it
    # starts "active" (shareable) — the dedicated draft-sharing tests build their own
    # draft-status agent instead of reusing this one.
    agent = create_agent(
        db,
        company_id=company_a.id,
        owner_id=owner.id,
        name="HR Analytics",
        description="Test agent",
        llm_model="test-model",
        custom_instructions=None,
    )
    agent.status = "active"

    draft_agent = create_agent(
        db,
        company_id=company_a.id,
        owner_id=owner.id,
        name="Draft Agent",
        description="Still being set up",
        llm_model="test-model",
        custom_instructions=None,
    )

    db.commit()
    for obj in (admin, owner, editor_target, viewer_target, outsider, inactive, company_b_user, agent, draft_agent):
        db.refresh(obj)

    return {
        "company_a": company_a,
        "company_b": company_b,
        "admin": admin,
        "owner": owner,
        "editor_target": editor_target,
        "viewer_target": viewer_target,
        "outsider": outsider,
        "inactive": inactive,
        "company_b_user": company_b_user,
        "agent": agent,
        "draft_agent": draft_agent,
    }
