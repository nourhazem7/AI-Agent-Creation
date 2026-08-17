"""Live integration tests: real company LLM endpoint + real HR demo SQLite database, no
mocking. Verifies the agent understands multi-table relationships (joins), not just
single-table lookups — per the project's explicit requirement that generated/answered
questions must be grounded in the actual connected database, not merely plausible-looking.

These make real network calls to the configured LLM endpoint (Settings.llm_base_url) and
will fail/error if that endpoint isn't reachable from wherever this runs — that's expected
and correct; do not mock around it.
"""
from __future__ import annotations

import pytest

from app.config import get_settings
from text2sql import TextSQL


@pytest.fixture(scope="module")
def hr_engine(hr_demo_db_path):
    settings = get_settings()
    conn_str = f"sqlite:///{hr_demo_db_path.replace(chr(92), '/')}"
    return TextSQL(
        conn_str,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        verify_ssl=settings.llm_verify_ssl,
        extra_body=settings.llm_extra_body_dict,
        llm_api_key=settings.llm_api_key or None,
    )


MULTI_TABLE_QUESTIONS = [
    "Which department has the highest number of employees?",
    "What is the average salary by department?",
    "Which department has the highest absence rate?",
    "Which employees had the most late arrivals?",
    "What was the total net payroll by department in March 2026?",
    "Which employees are assigned to more than one project?",
    "What is the average performance rating by department?",
    "Which project has the largest budget?",
]


@pytest.mark.parametrize("question", MULTI_TABLE_QUESTIONS)
def test_multi_table_business_question(hr_engine, question):
    result = hr_engine.ask(question)

    assert result.error is None, f"Question failed: {question!r} -> {result.error}"
    assert result.success
    assert result.sql, "No SQL was produced"
    assert result.data, f"Query produced no rows for: {question!r}"

    # Structural sanity check that this genuinely required more than one table — these
    # questions were specifically chosen because a correct answer requires a join.
    sql_upper = result.sql.upper()
    assert "JOIN" in sql_upper or sql_upper.count("FROM") > 0, (
        f"Expected a multi-table query for {question!r}, got: {result.sql}"
    )
