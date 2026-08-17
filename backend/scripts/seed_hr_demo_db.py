#!/usr/bin/env python
"""Builds backend/storage/demo/agent_one_hr_demo.db from the committed HR demo SQL dump
(agent_one_hr_demo.sql) — the project's controlled multi-table integration-test database
(companies/departments/employees/attendance/leave_requests/payroll/performance_reviews/
projects/employee_projects). Used to verify the agent actually understands multi-table
relationships (joins across departments/employees/payroll/etc.), not just single-table lookups.

Usage:
    backend/.venv/Scripts/python.exe backend/scripts/seed_hr_demo_db.py
"""
from __future__ import annotations

import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
SQL_PATH = os.path.join(HERE, "agent_one_hr_demo.sql")
DB_PATH = os.path.abspath(os.path.join(HERE, "..", "storage", "demo", "agent_one_hr_demo.db"))

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

with open(SQL_PATH, "r", encoding="utf-8") as f:
    sql_script = f.read()

conn = sqlite3.connect(DB_PATH)
try:
    conn.executescript(sql_script)
    conn.commit()
finally:
    conn.close()

print(f"HR demo database ready at: {DB_PATH}")
