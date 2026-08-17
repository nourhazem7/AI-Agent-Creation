"""Runs the actual dev seed script (backend/scripts/seed_sharing_demo.py) as a subprocess
against its own throwaway sqlite file — fully isolated from the shared test database used
by test_agent_sharing.py — and inspects the resulting rows directly. This validates the
script developers actually run, not a reimplementation of it.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from cryptography.fernet import Fernet

BACKEND_DIR = Path(__file__).resolve().parent.parent
SEED_SCRIPT = BACKEND_DIR / "scripts" / "seed_sharing_demo.py"


def test_seed_script_creates_expected_agent_shares(tmp_path):
    import sqlite3

    db_path = tmp_path / "seed_test.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path.as_posix()}",
        "FERNET_KEY": Fernet.generate_key().decode(),
    }
    result = subprocess.run(
        [sys.executable, str(SEED_SCRIPT)],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"seed script failed:\nstdout={result.stdout}\nstderr={result.stderr}"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT id, name, status, owner_id FROM agents ORDER BY created_at")
    agents = [dict(r) for r in cur.fetchall()]
    active_agents = [a for a in agents if a["status"] == "active"]
    draft_agents = [a for a in agents if a["status"] == "draft"]
    assert len(active_agents) == 1, f"expected exactly one active seeded agent, got {agents}"
    assert len(draft_agents) == 1, f"expected exactly one draft seeded agent, got {agents}"

    cur.execute("SELECT id, email, role FROM users")
    users_by_id = {r["id"]: dict(r) for r in cur.fetchall()}

    active_agent_id = active_agents[0]["id"]
    cur.execute("SELECT user_id, role, shared_by_id FROM agent_shares WHERE agent_id = ?", (active_agent_id,))
    shares = [dict(r) for r in cur.fetchall()]
    assert len(shares) == 2, f"expected exactly 2 shares on the active agent, got {shares}"

    by_role = {s["role"]: s for s in shares}
    assert users_by_id[by_role["editor"]["user_id"]]["email"] == "editor@sharing-demo.dev"
    assert users_by_id[by_role["editor"]["shared_by_id"]]["email"] == "owner@sharing-demo.dev"
    assert users_by_id[by_role["viewer"]["user_id"]]["email"] == "viewer@sharing-demo.dev"
    assert users_by_id[by_role["viewer"]["shared_by_id"]]["email"] == "admin@sharing-demo.dev"

    # The draft agent must have no shares at all.
    draft_agent_id = draft_agents[0]["id"]
    cur.execute("SELECT COUNT(*) AS n FROM agent_shares WHERE agent_id = ?", (draft_agent_id,))
    assert cur.fetchone()["n"] == 0

    conn.close()
