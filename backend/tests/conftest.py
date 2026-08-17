from __future__ import annotations

import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(TESTS_DIR, ".."))
HR_DB_PATH = os.path.join(BACKEND_DIR, "storage", "demo", "agent_one_hr_demo.db")
ECOMMERCE_DB_PATH = os.path.join(BACKEND_DIR, "storage", "demo", "demo_ecommerce.db")


@pytest.fixture(scope="session")
def hr_demo_db_path() -> str:
    """Rebuilds the HR demo database fresh from the committed SQL dump before tests run,
    so this fixture is reproducible on any machine — never a random pre-existing file."""
    seed_script = os.path.join(BACKEND_DIR, "scripts", "seed_hr_demo_db.py")
    subprocess.run([sys.executable, seed_script], check=True, cwd=BACKEND_DIR)
    assert os.path.exists(HR_DB_PATH)
    return HR_DB_PATH


@pytest.fixture(scope="session")
def hr_demo_connection_string(hr_demo_db_path: str) -> str:
    # Forward slashes work fine for SQLite connection strings on Windows too.
    return f"sqlite:///{hr_demo_db_path.replace(os.sep, '/')}"


@pytest.fixture(scope="session")
def ecommerce_demo_db_path() -> str:
    """A second, structurally different demo database — used to prove that two different
    agents pointed at two different databases never share a TextSQL engine."""
    seed_script = os.path.join(BACKEND_DIR, "scripts", "seed_demo_db.py")
    subprocess.run([sys.executable, seed_script], check=True, cwd=BACKEND_DIR)
    assert os.path.exists(ECOMMERCE_DB_PATH)
    return ECOMMERCE_DB_PATH


@pytest.fixture(scope="session")
def ecommerce_demo_connection_string(ecommerce_demo_db_path: str) -> str:
    return f"sqlite:///{ecommerce_demo_db_path.replace(os.sep, '/')}"


@pytest.fixture()
def app_db(tmp_path):
    """A fresh, isolated Agent One application database (Company/User/Agent/... tables) for
    each test — completely separate from the real dev database at backend/data/agentforge.db,
    so tests never touch or risk the real agents A/B/C."""
    from app.database import Base

    db_path = tmp_path / "test_agentforge.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine)
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def company(app_db):
    from app.repositories.company_repository import create_company

    c = create_company(app_db, name="Test Co")
    app_db.commit()
    return c


@pytest.fixture()
def user(app_db, company):
    from app.repositories.user_repository import create_user

    u = create_user(app_db, company_id=company.id, email="tester@example.com", hashed_password="x")
    app_db.commit()
    return u
