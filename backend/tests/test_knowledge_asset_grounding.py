"""Deterministic tests for the accuracy/grounding verification layer added on top of
knowledge asset generation — no LLM calls needed, these test the verification mechanism
itself against the real HR demo database's live metadata.
"""
from __future__ import annotations

import copy

from app.integrations import text2sql_adapter


class TestSchemaVerification:
    def test_live_introspection_matches_itself(self, hr_demo_connection_string):
        schema = text2sql_adapter.introspect_schema(hr_demo_connection_string)
        # A schema introspected from the real DB must verify clean against a second,
        # independent live read of the same DB.
        issues = text2sql_adapter.verify_schema_against_live(schema, hr_demo_connection_string)
        assert issues == []

    def test_detects_invented_table(self, hr_demo_connection_string):
        schema = text2sql_adapter.introspect_schema(hr_demo_connection_string)
        tampered = copy.deepcopy(schema)
        tampered["bonuses_that_do_not_exist"] = {
            "columns": [{"name": "id", "type": "INTEGER", "nullable": False, "comment": ""}],
            "primary_keys": ["id"],
            "foreign_keys": [],
            "comment": "",
        }
        issues = text2sql_adapter.verify_schema_against_live(tampered, hr_demo_connection_string)
        assert any("bonuses_that_do_not_exist" in i for i in issues)

    def test_detects_missing_table(self, hr_demo_connection_string):
        schema = text2sql_adapter.introspect_schema(hr_demo_connection_string)
        tampered = copy.deepcopy(schema)
        del tampered["employees"]
        issues = text2sql_adapter.verify_schema_against_live(tampered, hr_demo_connection_string)
        assert any("employees" in i for i in issues)

    def test_detects_invented_column(self, hr_demo_connection_string):
        schema = text2sql_adapter.introspect_schema(hr_demo_connection_string)
        tampered = copy.deepcopy(schema)
        tampered["employees"]["columns"].append(
            {"name": "made_up_bonus_percent", "type": "REAL", "nullable": True, "comment": ""}
        )
        issues = text2sql_adapter.verify_schema_against_live(tampered, hr_demo_connection_string)
        assert any("made_up_bonus_percent" in i for i in issues)

    def test_detects_wrong_primary_key(self, hr_demo_connection_string):
        schema = text2sql_adapter.introspect_schema(hr_demo_connection_string)
        tampered = copy.deepcopy(schema)
        tampered["departments"]["primary_keys"] = ["department_name"]
        issues = text2sql_adapter.verify_schema_against_live(tampered, hr_demo_connection_string)
        assert any("primary key" in i for i in issues)

    def test_detects_invented_foreign_key(self, hr_demo_connection_string):
        schema = text2sql_adapter.introspect_schema(hr_demo_connection_string)
        tampered = copy.deepcopy(schema)
        tampered["projects"]["foreign_keys"].append(
            {"constrained_columns": ["client_name"], "referred_table": "companies", "referred_columns": ["company_id"]}
        )
        issues = text2sql_adapter.verify_schema_against_live(tampered, hr_demo_connection_string)
        assert any("foreign key" in i for i in issues)


class TestDocumentationGrounding:
    def _schema(self, hr_demo_connection_string):
        return text2sql_adapter.introspect_schema(hr_demo_connection_string)

    def test_accepts_real_references(self, hr_demo_connection_string):
        schema = self._schema(hr_demo_connection_string)
        markdown = (
            "# Overview\n"
            "The `employees` table links to `departments` via `employees.department_id`.\n"
            "The `attendance` table tracks daily check-ins.\n"
        )
        unsupported = text2sql_adapter.validate_documentation_grounding(markdown, schema)
        assert unsupported == []

    def test_rejects_invented_table(self, hr_demo_connection_string):
        schema = self._schema(hr_demo_connection_string)
        markdown = "The `bonuses` table tracks employee bonuses.\n"
        unsupported = text2sql_adapter.validate_documentation_grounding(markdown, schema)
        assert len(unsupported) == 1
        assert "bonuses" in unsupported[0]

    def test_rejects_invented_column_on_real_table(self, hr_demo_connection_string):
        schema = self._schema(hr_demo_connection_string)
        markdown = "See `employees.loyalty_points` for details.\n"
        unsupported = text2sql_adapter.validate_documentation_grounding(markdown, schema)
        assert len(unsupported) == 1
        assert "loyalty_points" in unsupported[0]

    def test_bare_column_reference_without_table_prefix_is_accepted(self, hr_demo_connection_string):
        schema = self._schema(hr_demo_connection_string)
        markdown = "The `salary` column stores compensation.\n"
        unsupported = text2sql_adapter.validate_documentation_grounding(markdown, schema)
        assert unsupported == []

    def test_sql_type_names_in_backticks_are_not_flagged(self, hr_demo_connection_string):
        # Regression test: describing a column's type in backticks (a normal, legitimate
        # writing convention) must not be treated as an invented schema reference.
        schema = self._schema(hr_demo_connection_string)
        markdown = (
            "The `hire_date` column is a `DATE`. The `late_flag` column is `INTEGER` "
            "(effectively `BOOLEAN`). `check_in` and `check_out` are `TIME` values, and "
            "may be `NULL` when an employee was absent. Example: `SELECT * FROM employees`."
        )
        unsupported = text2sql_adapter.validate_documentation_grounding(markdown, schema)
        assert unsupported == []


class TestSqlValidation:
    def test_valid_select_passes(self, hr_demo_connection_string):
        ok, error = text2sql_adapter.validate_sql_against_db(
            hr_demo_connection_string, "SELECT COUNT(*) FROM employees"
        )
        assert ok is True
        assert error is None

    def test_invalid_table_fails(self, hr_demo_connection_string):
        ok, error = text2sql_adapter.validate_sql_against_db(
            hr_demo_connection_string, "SELECT * FROM tables_that_do_not_exist"
        )
        assert ok is False
        assert error is not None

    def test_destructive_sql_is_rejected_before_execution(self, hr_demo_connection_string):
        ok, error = text2sql_adapter.validate_sql_against_db(
            hr_demo_connection_string, "DELETE FROM employees"
        )
        assert ok is False
        assert "Rejected" in error

    def test_real_multi_table_join_passes(self, hr_demo_connection_string):
        ok, error = text2sql_adapter.validate_sql_against_db(
            hr_demo_connection_string,
            "SELECT d.department_name, COUNT(*) FROM employees e "
            "JOIN departments d ON e.department_id = d.department_id GROUP BY d.department_name",
        )
        assert ok is True, error
