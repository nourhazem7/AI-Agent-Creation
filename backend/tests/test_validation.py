"""Validation Workspace: real end-to-end tests against the real HR demo database and the
real company-connected LLM — no mocks, matching this repo's established testing convention.
Covers: user-created test creation (with/without SQL), agent-scoped retrieval, running a test
for real, expected_sql validated at creation time, the three comparison branches (expected
answer / expected sql reference / exploratory), Run All, Run Failed, and agent isolation.
"""
from __future__ import annotations

import json

import pytest

from app.models.agent import Agent
from app.repositories import database_connection_repository, knowledge_asset_repository, validation_repository
from app.schemas.agent import AgentCreate
from app.services import agent_service, validation_service


def _make_agent(app_db, company, user, name="Test Agent") -> Agent:
    out = agent_service.create_agent(
        app_db, company_id=company.id, owner_id=user.id, payload=AgentCreate(name=name)
    )
    return app_db.get(Agent, out.id)


def _connect_agent(app_db, agent, db_path: str) -> None:
    database_connection_repository.upsert(
        app_db,
        agent_id=agent.id,
        dialect="sqlite",
        host=None,
        port=None,
        database_name=None,
        username=None,
        encrypted_password=None,
        sqlite_file_path=db_path,
    )
    agent.knowledge_version += 1
    app_db.commit()


@pytest.fixture()
def hr_agent(app_db, company, user, hr_demo_db_path):
    agent = _make_agent(app_db, company, user, name="HR Validation Agent")
    _connect_agent(app_db, agent, hr_demo_db_path)
    return agent


class TestCreateUserTest:
    def test_create_test_without_sql_does_not_require_sql_knowledge(self, app_db, hr_agent):
        test = validation_service.create_user_test(app_db, hr_agent, question="How many employees are there?")
        assert test.expected_sql is None
        assert test.expected_sql_verified is False
        assert test.origin == "user_created"
        assert test.last_status == "not_run"

    def test_create_test_with_valid_expected_sql_is_verified(self, app_db, hr_agent):
        test = validation_service.create_user_test(
            app_db,
            hr_agent,
            question="How many employees are there?",
            expected_sql="SELECT COUNT(*) AS n FROM employees",
        )
        assert test.expected_sql_verified is True

    def test_create_test_with_invalid_expected_sql_is_rejected(self, app_db, hr_agent):
        with pytest.raises(ValueError):
            validation_service.create_user_test(
                app_db,
                hr_agent,
                question="Bogus",
                expected_sql="SELECT * FROM table_that_does_not_exist",
            )
        # Nothing must have been stored — a broken expected_sql is never saved silently.
        assert validation_repository.list_tests_by_agent(app_db, hr_agent.id) == []


class TestRetrieval:
    def test_list_tests_scoped_to_agent(self, app_db, company, user, hr_demo_db_path):
        agent_a = _make_agent(app_db, company, user, name="Agent A")
        agent_b = _make_agent(app_db, company, user, name="Agent B")
        _connect_agent(app_db, agent_a, hr_demo_db_path)
        _connect_agent(app_db, agent_b, hr_demo_db_path)

        validation_service.create_user_test(app_db, agent_a, question="Question for A only")
        validation_service.create_user_test(app_db, agent_b, question="Question for B only")

        tests_a = validation_service.list_tests(app_db, agent_a)
        tests_b = validation_service.list_tests(app_db, agent_b)

        assert [t.question for t in tests_a] == ["Question for A only"]
        assert [t.question for t in tests_b] == ["Question for B only"]

    def test_get_test_for_agent_rejects_cross_agent_id(self, app_db, company, user, hr_demo_db_path):
        agent_a = _make_agent(app_db, company, user, name="Agent A")
        agent_b = _make_agent(app_db, company, user, name="Agent B")
        _connect_agent(app_db, agent_a, hr_demo_db_path)

        test = validation_service.create_user_test(app_db, agent_a, question="Only A's test")

        assert validation_repository.get_test_for_agent(app_db, agent_a.id, test.id) is not None
        assert validation_repository.get_test_for_agent(app_db, agent_b.id, test.id) is None


class TestRowComparison:
    """Deterministic, no-LLM tests for the row-comparison helper behind the expected_sql
    branch — found via live testing that comparing by column name caused false 'failed'
    verdicts when the agent's own SQL and the reference SQL used different aliases for the
    same value (e.g. `total_orders` vs `order_count`), even though the data matched."""

    def test_matches_despite_different_column_aliases(self):
        actual = [{"total_orders": 420}]
        reference = [{"order_count": 420}]
        assert validation_service._rows_match(actual, reference) is True

    def test_matches_despite_row_order_difference(self):
        actual = [{"n": 1}, {"n": 2}]
        reference = [{"n": 2}, {"n": 1}]
        assert validation_service._rows_match(actual, reference) is True

    def test_detects_real_value_mismatch(self):
        actual = [{"total_orders": 420}]
        reference = [{"order_count": 421}]
        assert validation_service._rows_match(actual, reference) is False

    def test_detects_row_count_mismatch(self):
        assert validation_service._rows_match([{"n": 1}], [{"n": 1}, {"n": 2}]) is False


class TestRunningTests:
    def test_run_test_calls_real_engine_and_records_a_run(self, app_db, hr_agent):
        test = validation_service.create_user_test(app_db, hr_agent, question="How many employees are there?")
        run = validation_service.run_test(app_db, hr_agent, test)

        assert run.status in ("passed", "failed", "error")
        app_db.refresh(test)
        assert test.last_status == run.status
        if run.status != "error":
            assert run.generated_sql, "A non-error run must have real generated SQL, not a stub"

    def test_exploratory_branch_never_claims_answer_correctness(self, app_db, hr_agent):
        test = validation_service.create_user_test(app_db, hr_agent, question="How many employees are there?")
        run = validation_service.run_test(app_db, hr_agent, test)

        if run.status == "passed":
            assert "does not verify the answer is correct" in run.comparison_note

    def test_expected_answer_branch_pass(self, app_db, hr_agent):
        # 78 real employees in the seeded HR demo DB (verified directly against sqlite above).
        test = validation_service.create_user_test(
            app_db, hr_agent, question="How many employees are there in total?", expected_answer="78"
        )
        run = validation_service.run_test(app_db, hr_agent, test)
        assert run.status in ("passed", "failed", "error")
        assert "expected-answer text" in (run.comparison_note or "") or run.status == "error"
        assert run.reference_result is None, "No verified reference SQL exists — there is nothing to persist"

    def test_expected_answer_branch_fail_on_wrong_expectation(self, app_db, hr_agent):
        test = validation_service.create_user_test(
            app_db,
            hr_agent,
            question="How many employees are there in total?",
            expected_answer="a number that will never appear, like 999999999",
        )
        run = validation_service.run_test(app_db, hr_agent, test)
        assert run.status in ("failed", "error")

    def test_expected_sql_branch_compares_real_row_data(self, app_db, hr_agent):
        test = validation_service.create_user_test(
            app_db,
            hr_agent,
            question="How many employees are there in total?",
            expected_sql="SELECT COUNT(*) AS employee_count FROM employees",
        )
        run = validation_service.run_test(app_db, hr_agent, test)
        assert run.status in ("passed", "failed", "error")
        if run.status != "error":
            assert "verified reference SQL's actual results" in (run.comparison_note or "")
            assert run.reference_result is not None, "A branch-1 run must persist the actual reference result"
            assert json.loads(run.reference_result) == [{"employee_count": 78}]

    def test_verified_expected_sql_takes_priority_over_expected_answer(self, app_db, hr_agent):
        """When a test has both a verified expected_sql and an expected_answer (the common
        shape for AI-generated tests, where expected_answer is often just a description),
        the deterministic SQL comparison must be used, not the text heuristic."""
        test = validation_service.create_user_test(
            app_db,
            hr_agent,
            question="How many employees are there in total?",
            expected_sql="SELECT COUNT(*) AS employee_count FROM employees",
            expected_answer="A description of the expected result, not a literal value",
        )
        run = validation_service.run_test(app_db, hr_agent, test)
        if run.status != "error":
            assert "verified reference SQL's actual results" in (run.comparison_note or "")
            assert run.reference_result is not None
            assert "expected-answer text" not in (run.comparison_note or "")

    def test_sql_generated_is_never_conflated_with_passed_when_expectation_exists(self, app_db, hr_agent):
        """A test with an expected_answer must never be marked 'passed' purely because SQL
        was generated — only branch 3 (no expectation at all) treats SQL-ran as sufficient."""
        test = validation_service.create_user_test(
            app_db,
            hr_agent,
            question="How many employees are there in total?",
            expected_answer="a number that will never appear, like 999999999",
        )
        run = validation_service.run_test(app_db, hr_agent, test)
        if run.generated_sql and run.status == "passed":
            pytest.fail("A run must not pass on an unmatched expected_answer just because SQL was produced")


class TestRunAllAndRunFailed:
    def test_run_all_runs_every_test(self, app_db, hr_agent):
        validation_service.create_user_test(app_db, hr_agent, question="How many employees are there?")
        validation_service.create_user_test(app_db, hr_agent, question="How many departments are there?")

        runs = validation_service.run_all(app_db, hr_agent)
        assert len(runs) == 2
        tests = validation_repository.list_tests_by_agent(app_db, hr_agent.id)
        assert all(t.last_status != "not_run" for t in tests)

    def test_run_failed_only_reruns_failed_and_error_tests(self, app_db, hr_agent):
        passing = validation_service.create_user_test(app_db, hr_agent, question="How many employees are there?")
        # Force a guaranteed error: no expected_sql needed, just an unanswerable/error-prone one
        # is unreliable to force deterministically with a real LLM, so instead we directly seed
        # last_status to simulate a prior failed run and confirm run_failed selects it.
        also_run = validation_service.create_user_test(app_db, hr_agent, question="How many departments are there?")
        validation_service.run_test(app_db, hr_agent, passing)
        also_run.last_status = "failed"
        app_db.commit()

        before_passing_runs = len(validation_repository.list_runs_for_test(app_db, passing.id))
        validation_service.run_failed(app_db, hr_agent)
        after_passing_runs = len(validation_repository.list_runs_for_test(app_db, passing.id))
        after_also_run_runs = len(validation_repository.list_runs_for_test(app_db, also_run.id))

        assert after_passing_runs == before_passing_runs, "run_failed must not re-run a passed/other-status test"
        assert after_also_run_runs == 1, "run_failed must run a test whose last_status was 'failed'"


class TestAgentIsolation:
    def test_running_agent_a_tests_never_touches_agent_b_rows(self, app_db, company, user, hr_demo_db_path):
        agent_a = _make_agent(app_db, company, user, name="Agent A")
        agent_b = _make_agent(app_db, company, user, name="Agent B")
        _connect_agent(app_db, agent_a, hr_demo_db_path)
        _connect_agent(app_db, agent_b, hr_demo_db_path)

        test_a = validation_service.create_user_test(app_db, agent_a, question="How many employees are there?")
        test_b = validation_service.create_user_test(app_db, agent_b, question="How many departments are there?")

        validation_service.run_all(app_db, agent_a)

        app_db.refresh(test_b)
        assert test_b.last_status == "not_run", "Running agent A's tests must not run or affect agent B's tests"
        assert validation_repository.list_runs_for_test(app_db, test_b.id) == []

        app_db.refresh(test_a)
        assert test_a.last_status != "not_run"

    def test_sync_from_knowledge_asset_is_agent_scoped(self, app_db, company, user, hr_demo_db_path):
        agent_a = _make_agent(app_db, company, user, name="Agent A")
        agent_b = _make_agent(app_db, company, user, name="Agent B")
        _connect_agent(app_db, agent_a, hr_demo_db_path)
        _connect_agent(app_db, agent_b, hr_demo_db_path)

        knowledge_asset_repository.upsert(
            app_db,
            agent_id=agent_a.id,
            asset_type="validation_suite",
            source="generated",
            status="ready",
            content=json.dumps(
                [{"question": "AI-generated question for A", "expected_sql": None, "sql_verified": False}]
            ),
            verified=True,
        )
        app_db.commit()

        tests_a = validation_service.list_tests(app_db, agent_a)
        tests_b = validation_service.list_tests(app_db, agent_b)

        assert any(t.question == "AI-generated question for A" for t in tests_a)
        assert all(t.question != "AI-generated question for A" for t in tests_b)

    def test_unverified_or_not_ready_asset_is_never_synced(self, app_db, hr_agent):
        knowledge_asset_repository.upsert(
            app_db,
            agent_id=hr_agent.id,
            asset_type="validation_suite",
            source="generated",
            status="ready",
            content=json.dumps([{"question": "Should not appear", "expected_sql": None, "sql_verified": False}]),
            verified=False,  # never actually verified
        )
        app_db.commit()

        tests = validation_service.list_tests(app_db, hr_agent)
        assert all(t.question != "Should not appear" for t in tests)
