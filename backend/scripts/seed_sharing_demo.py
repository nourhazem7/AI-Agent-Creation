#!/usr/bin/env python
"""Development-only fixture for exercising Agent Sharing & Access locally.

Registration always creates a brand-new company, so two real accounts can never land in
the same company through the normal signup flow — which makes it impossible to click
through sharing by hand. This script seeds one scenario directly against the configured
DATABASE_URL so you can log in as each user and see the feature from every angle.

Not wired into app startup, not used by any test (tests build their own isolated scenario
in backend/tests/conftest.py). Safe to re-run — it clears its own dev users/company first.

Usage:
    backend/.venv/Scripts/python.exe backend/scripts/seed_sharing_demo.py

All accounts share the password printed below. These are local dev credentials only —
never used outside this seed script, never real secrets.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from sqlalchemy import select  # noqa: E402

import app.models  # noqa: E402,F401 - register every model before create_all()
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models.agent import Agent  # noqa: E402
from app.models.agent_share import AgentShare  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.user import User  # noqa: E402
from app.repositories.agent_repository import create_agent  # noqa: E402
from app.repositories.company_repository import create_company  # noqa: E402
from app.repositories.user_repository import create_user  # noqa: E402
from app.security import hash_password  # noqa: E402

DEV_PASSWORD = "dev-password-only"  # not a real secret — local seed data only

COMPANY_A_NAME = "[Dev Seed] Sharing Demo Co"
COMPANY_B_NAME = "[Dev Seed] Other Company Co"


def _wipe_previous_seed(db) -> None:
    for company_name in (COMPANY_A_NAME, COMPANY_B_NAME):
        company = db.execute(select(Company).where(Company.name == company_name)).scalar_one_or_none()
        if company:
            db.delete(company)  # cascades to users/agents/shares
    db.commit()


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _wipe_previous_seed(db)

        company_a = create_company(db, name=COMPANY_A_NAME)
        company_b = create_company(db, name=COMPANY_B_NAME)

        def _user(company_id: str, email: str, full_name: str, role: str = "member") -> User:
            return create_user(
                db,
                company_id=company_id,
                email=email,
                hashed_password=hash_password(DEV_PASSWORD),
                full_name=full_name,
                role=role,
            )

        admin = _user(company_a.id, "admin@sharing-demo.dev", "Omar (Admin)", role="admin")
        owner = _user(company_a.id, "owner@sharing-demo.dev", "Ahmed (Owner)")
        editor = _user(company_a.id, "editor@sharing-demo.dev", "Sara (Editor)")
        viewer = _user(company_a.id, "viewer@sharing-demo.dev", "Omar Khaled (Viewer)")
        no_access = _user(company_a.id, "noaccess@sharing-demo.dev", "Nadia (No Access)")
        other_company_user = _user(company_b.id, "user@other-company.dev", "Layla (Company B)", role="admin")

        agent = create_agent(
            db,
            company_id=company_a.id,
            owner_id=owner.id,
            name="HR Analytics Agent",
            description="Seeded for manual sharing/access testing.",
            llm_model="test-model",
            custom_instructions=None,
        )
        # Sharing only takes effect once an agent is actually Ready (see
        # app.models.agent.SHAREABLE_STATUSES) — jump straight there so the shares below
        # are live and testable, without re-running the (unrelated, untouched) setup wizard.
        agent.status = "active"

        draft_agent = create_agent(
            db,
            company_id=company_a.id,
            owner_id=owner.id,
            name="Sales Pipeline Agent (Draft)",
            description="Left in draft — for verifying draft agents can't be shared.",
            llm_model="test-model",
            custom_instructions=None,
        )
        db.commit()

        db.add(AgentShare(agent_id=agent.id, user_id=editor.id, role="editor", shared_by_id=owner.id))
        db.add(AgentShare(agent_id=agent.id, user_id=viewer.id, role="viewer", shared_by_id=admin.id))
        db.commit()

        print(f"Seed complete. All accounts use password: {DEV_PASSWORD}\n")
        print(f"Company A ({COMPANY_A_NAME}):")
        print(f"  admin (company admin, full access)........ {admin.email}")
        print(f"  owner (owns 'HR Analytics Agent')........... {owner.email}")
        print(f"  editor (shared as editor by the owner)...... {editor.email}")
        print(f"  viewer (shared as viewer by the admin)...... {viewer.email}")
        print(f"  no_access (company member, not shared)...... {no_access.email}")
        print(f"\nCompany B ({COMPANY_B_NAME}) — for cross-company negative testing:")
        print(f"  {other_company_user.email}")
        print(f"\nAgent id (status=active, shared): {agent.id}")
        print(f"Draft agent id (status=draft, unshared, owner-only): {draft_agent.id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
