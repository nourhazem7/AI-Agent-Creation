"""Validation Workspace: real end-to-end tests against the real HR demo database and the real
company-connected LLM — no mocks, matching this repo's established testing convention.

Covers: user-created test creation (with/without SQL/criteria), agent-scoped retrieval, running
a test for real, the business-answer judge (independent assessment + reference-as-diagnostic-
evidence reconciliation), Run All, Run Failed, and agent isolation. The judge tests are built
directly from the real failure examples found during manual testing against the HR and Sales
Analytics databases: an agent correctly narrowing to what the question asked for while a
reference over-broadens; identical data under different column order/aliases; a reference that
executes but returns nothing while the agent is right; and empty-vs-empty never auto-passing.
"""
from __future__ import annotations

import inspect
import json

import pytest

from app.integrations import text2sql_adapter
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


@pytest.fixture(scope="session")
def hr_schema_summary(hr_demo_connection_string):
    return text2sql_adapter.introspect_schema(hr_demo_connection_string)


_RUN_STATUSES = {"passed", "partial", "failed", "error", "inconclusive"}


class TestCreateUserTest:
    def test_create_test_without_sql_does_not_require_sql_knowledge(self, app_db, hr_agent):
        test = validation_service.create_user_test(app_db, hr_agent, question="How many employees are there?")
        assert test.expected_sql is None
        assert test.expected_sql_verified is False
        assert test.criteria is None
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

    def test_create_test_with_criteria_stores_it_verbatim(self, app_db, hr_agent):
        test = validation_service.create_user_test(
            app_db,
            hr_agent,
            question="How many employees are there in the Engineering department?",
            criteria="Must restrict to the Engineering department only.",
        )
        assert test.criteria == "Must restrict to the Engineering department only."


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


class TestJudgeParsingHelpers:
    """Deterministic, no-LLM tests for the judge's response-parsing safety net: a malformed or
    off-schema response must never silently become 'passed'."""

    def test_valid_json_is_accepted(self):
        parsed = text2sql_adapter._extract_judge_json(
            'Here is my answer: {"verdict": "passed", "reasoning": "ok", "violated_requirement": null}'
        )
        assert parsed == {"verdict": "passed", "reasoning": "ok", "violated_requirement": None}

    def test_unparseable_text_returns_none(self):
        assert text2sql_adapter._extract_judge_json("not json at all") is None

    def test_coerce_verdict_falls_back_to_inconclusive_never_passed(self):
        result = text2sql_adapter._coerce_verdict(None, fallback_note="parse failed")
        assert result["verdict"] == "inconclusive"
        assert result["reasoning"] == "parse failed"

    def test_coerce_verdict_rejects_off_schema_verdict(self):
        result = text2sql_adapter._coerce_verdict(
            {"verdict": "sort-of-passed", "reasoning": "hmm"}, fallback_note="fallback"
        )
        assert result["verdict"] == "inconclusive"

    def test_no_hardcoded_row_comparison_shortcut_in_run_test(self):
        """Regression guard: run_test must never contain a row-count/row-equality shortcut
        (e.g. auto-passing when both the agent's and the reference's results are empty) —
        every verdict must come from the judge, which reasons about plausibility instead of
        comparing row sets directly."""
        source = inspect.getsource(validation_service.run_test)
        assert "_rows_match" not in source
        assert "_answer_contains" not in source
        assert "len(reference_rows)" not in source
        assert "len(result.data)" not in source


class TestJudgeLive:
    """Real LLM calls to text2sql_adapter.judge_business_answer directly (bypassing the full
    agentic ask() loop for speed/determinism of the *setup*), built from the exact failure
    patterns found in manual testing. These assert properties/tiers, not exact wording, since
    a live LLM judge has some inherent variance even at temperature 0.
    """

    def test_narrow_correct_answer_not_penalized_for_differing_from_broad_reference(self, hr_schema_summary):
        """Mirrors the real 'payment methods' failure: the agent correctly narrowed to what was
        asked; a reference query covering a broader scope must not cause a failure."""
        verdict = text2sql_adapter.judge_business_answer(
            "openai:Qwen/Qwen3.6-35B-A3B",
            question="What is the headcount of the Engineering and Sales departments only?",
            schema_summary=hr_schema_summary,
            agent_sql="SELECT department_name, COUNT(*) AS headcount FROM employees JOIN departments "
            "ON employees.department_id = departments.department_id "
            "WHERE department_name IN ('Engineering', 'Sales') GROUP BY department_name",
            agent_commentary="Engineering has 12 employees and Sales has 9 employees.",
            agent_rows=[{"department_name": "Engineering", "headcount": 12}, {"department_name": "Sales", "headcount": 9}],
            criteria=None,
            expected_answer=None,
            reference_sql="SELECT department_name, COUNT(*) AS headcount FROM employees JOIN departments "
            "ON employees.department_id = departments.department_id GROUP BY department_name",
            reference_rows=[
                {"department_name": "Engineering", "headcount": 12},
                {"department_name": "Sales", "headcount": 9},
                {"department_name": "Marketing", "headcount": 5},
                {"department_name": "Finance", "headcount": 4},
            ],
        )
        assert verdict["verdict"] in _RUN_STATUSES
        assert verdict["verdict"] != "failed", (
            f"Correctly narrowing to exactly what was asked must not fail just because a "
            f"broader reference exists. Reasoning: {verdict['reasoning']}"
        )

    def test_identical_data_different_column_order_and_aliases_passes(self, hr_schema_summary):
        """Mirrors the real 'product category' failure: same numbers, different column order —
        must not be treated as a mismatch."""
        verdict = text2sql_adapter.judge_business_answer(
            "openai:Qwen/Qwen3.6-35B-A3B",
            question="For each department, how many employees are there and what is the average salary?",
            schema_summary=hr_schema_summary,
            agent_sql="SELECT department_name, avg_salary, headcount FROM dept_stats",
            agent_commentary="Here are the headcount and average salary per department.",
            agent_rows=[
                {"department_name": "Engineering", "avg_salary": 95000, "headcount": 12},
                {"department_name": "Sales", "avg_salary": 72000, "headcount": 9},
            ],
            criteria=None,
            expected_answer=None,
            reference_sql="SELECT department_name, headcount, avg_salary FROM dept_stats_v2",
            reference_rows=[
                {"department_name": "Sales", "headcount": 9, "avg_salary": 72000},
                {"department_name": "Engineering", "headcount": 12, "avg_salary": 95000},
            ],
        )
        assert verdict["verdict"] == "passed", (
            f"Identical data under different column order/aliases/row order must pass. "
            f"Reasoning: {verdict['reasoning']}"
        )

    def test_reference_returns_nothing_agent_is_correct_and_not_penalized(self, hr_schema_summary):
        """Mirrors the real 'department managers' failure: the reference query executed but
        returned zero rows (it was the wrong query); the agent's real, populated answer must
        not be penalized for disagreeing with a reference that's plausibly wrong."""
        verdict = text2sql_adapter.judge_business_answer(
            "openai:Qwen/Qwen3.6-35B-A3B",
            question="Who are the managers of each department, and what company do those departments belong to?",
            schema_summary=hr_schema_summary,
            agent_sql="SELECT d.department_name, c.company_name, e.first_name, e.last_name FROM departments d "
            "JOIN companies c ON d.company_id = c.company_id "
            "JOIN employees e ON d.manager_employee_id = e.employee_id",
            agent_commentary="Each department's manager and company are listed below.",
            agent_rows=[
                {"department_name": "Engineering", "company_name": "Nexa Technologies", "first_name": "Sara", "last_name": "Mostafa"},
                {"department_name": "Human Resources", "company_name": "Nexa Technologies", "first_name": "Jana", "last_name": "Younis"},
            ],
            criteria=None,
            expected_answer=None,
            reference_sql="SELECT * FROM departments WHERE manager_id IS NOT NULL",  # wrong column name, matches nothing
            reference_rows=[],
        )
        assert verdict["verdict"] != "failed", (
            f"Agent should not fail just because a reference solution (which returned nothing) "
            f"disagrees. Reasoning: {verdict['reasoning']}"
        )

    def test_empty_vs_empty_does_not_auto_pass_when_implausible(self, hr_schema_summary):
        """Both sides returning zero rows proves nothing about correctness on its own — for a
        question where zero is clearly implausible given the schema, the judge must not treat
        matching emptiness as evidence of a correct answer."""
        verdict = text2sql_adapter.judge_business_answer(
            "openai:Qwen/Qwen3.6-35B-A3B",
            question="How many employees work in the Engineering department?",
            schema_summary=hr_schema_summary,
            agent_sql="SELECT COUNT(*) AS n FROM employees WHERE department_id = 999999",  # bad id, matches nothing
            agent_commentary="There are 0 employees in the Engineering department.",
            agent_rows=[{"n": 0}],
            criteria=None,
            expected_answer=None,
            reference_sql="SELECT COUNT(*) AS n FROM employees WHERE department_id = -1",  # also wrong, also empty
            reference_rows=[{"n": 0}],
        )
        # The real HR demo DB has a real, populated Engineering department, so an answer of 0
        # is implausible — the judge must reason this, not default to "passed" because both
        # sides happened to agree on an empty/zero result.
        assert verdict["verdict"] != "passed", (
            f"Matching (and implausible) zero-employee results from two independently-wrong "
            f"queries must not be treated as a correct answer. Reasoning: {verdict['reasoning']}"
        )

    def test_no_reference_skips_stage_two_entirely(self, hr_schema_summary):
        verdict = text2sql_adapter.judge_business_answer(
            "openai:Qwen/Qwen3.6-35B-A3B",
            question="How many employees are there in total?",
            schema_summary=hr_schema_summary,
            agent_sql="SELECT COUNT(*) AS n FROM employees",
            agent_commentary="There are 78 employees in total.",
            agent_rows=[{"n": 78}],
            criteria=None,
            expected_answer=None,
            reference_sql=None,
            reference_rows=None,
        )
        assert verdict["verdict"] in _RUN_STATUSES
        # No reconciliation pass ran, so the reasoning must not carry the stage-2 transparency
        # prefix that only appears when a reference was actually reviewed.
        assert "diagnostic reference solution" not in verdict["reasoning"]

    def test_criteria_is_authoritative_and_can_fail_a_result_expected_answer_would_have_passed(self, hr_schema_summary):
        verdict = text2sql_adapter.judge_business_answer(
            "openai:Qwen/Qwen3.6-35B-A3B",
            question="How many employees are there in total?",
            schema_summary=hr_schema_summary,
            agent_sql="SELECT COUNT(*) AS n FROM employees WHERE is_active = 1",
            agent_commentary="There are 70 active employees.",
            agent_rows=[{"n": 70}],
            criteria="Must count ALL employees regardless of active status, not just active ones.",
            expected_answer=None,
            reference_sql=None,
            reference_rows=None,
        )
        assert verdict["verdict"] != "passed", (
            f"An explicit authoritative criteria that the result violates must prevent a pass. "
            f"Reasoning: {verdict['reasoning']}"
        )


class TestRunningTests:
    def test_run_test_calls_real_engine_and_records_a_run(self, app_db, hr_agent):
        test = validation_service.create_user_test(app_db, hr_agent, question="How many employees are there?")
        run = validation_service.run_test(app_db, hr_agent, test)

        assert run.status in _RUN_STATUSES
        app_db.refresh(test)
        assert test.last_status == run.status
        if run.status != "error":
            assert run.generated_sql, "A non-error run must have real generated SQL, not a stub"
            assert run.agent_answer, "A non-error run must persist the agent's own NL commentary"

    def test_technical_failure_skips_the_judge(self, app_db, company, user):
        """An agent with no database connection can't produce a real result, so run_test must
        stop at the deterministic technical-error tier and never invoke the judge."""
        agent = _make_agent(app_db, company, user, name="No DB Agent")
        test = validation_service.create_user_test(app_db, agent, question="How many employees are there?")
        run = validation_service.run_test(app_db, agent, test)
        assert run.status == "error"
        assert run.agent_answer is None
        assert run.reference_result is None

    def test_verified_expected_sql_populates_reference_result(self, app_db, hr_agent):
        test = validation_service.create_user_test(
            app_db,
            hr_agent,
            question="How many employees are there in total?",
            expected_sql="SELECT COUNT(*) AS employee_count FROM employees",
        )
        run = validation_service.run_test(app_db, hr_agent, test)
        if run.status != "error":
            assert run.reference_result is not None
            assert json.loads(run.reference_result) == [{"employee_count": 78}]

    def test_no_expected_sql_means_no_reference_result(self, app_db, hr_agent):
        test = validation_service.create_user_test(app_db, hr_agent, question="How many employees are there?")
        run = validation_service.run_test(app_db, hr_agent, test)
        assert run.reference_result is None


class TestRunAllAndRunFailed:
    def test_run_all_runs_every_test(self, app_db, hr_agent):
        validation_service.create_user_test(app_db, hr_agent, question="How many employees are there?")
        validation_service.create_user_test(app_db, hr_agent, question="How many departments are there?")

        runs = validation_service.run_all(app_db, hr_agent)
        assert len(runs) == 2
        tests = validation_repository.list_tests_by_agent(app_db, hr_agent.id)
        assert all(t.last_status != "not_run" for t in tests)

    def test_run_failed_reruns_failed_partial_error_and_inconclusive_tests(self, app_db, hr_agent):
        passing = validation_service.create_user_test(app_db, hr_agent, question="How many employees are there?")
        also_run = validation_service.create_user_test(app_db, hr_agent, question="How many departments are there?")
        untouched = validation_service.create_user_test(app_db, hr_agent, question="How many companies are there?")
        validation_service.run_test(app_db, hr_agent, passing)
        also_run.last_status = "partial"
        untouched.last_status = "passed"
        app_db.commit()

        before_passing_runs = len(validation_repository.list_runs_for_test(app_db, passing.id))
        before_untouched_runs = len(validation_repository.list_runs_for_test(app_db, untouched.id))
        validation_service.run_failed(app_db, hr_agent)
        after_passing_runs = len(validation_repository.list_runs_for_test(app_db, passing.id))
        after_untouched_runs = len(validation_repository.list_runs_for_test(app_db, untouched.id))
        after_also_run_runs = len(validation_repository.list_runs_for_test(app_db, also_run.id))

        assert after_passing_runs == before_passing_runs, "run_failed must not re-run a passed/other-status test"
        assert after_untouched_runs == before_untouched_runs, "run_failed must not re-run a passed test"
        assert after_also_run_runs == 1, "run_failed must re-run a test whose last_status was 'partial'"


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
