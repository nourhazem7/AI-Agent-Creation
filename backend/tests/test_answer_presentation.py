"""Deterministic Chat answer presentation — pure function tests, no LLM, no mocking needed
(there's nothing external to mock). Fixtures are the real result_data shapes captured live
against the Sales Analytics and HR Analytics demo databases during development (see
app/services/answer_presentation.py's module docstring for where each shape came from), plus
a couple of end-to-end integration tests confirming chat_service.send_message actually wires
this in and no longer makes a second LLM call.

A single value/row stays one short sentence. Anything with more than one row must render as
an intro line followed by one bullet ("•") per item — never a dense multi-row paragraph.
"""
from __future__ import annotations

import time

import pytest

from app.repositories import conversation_repository, database_connection_repository
from app.schemas.agent import AgentCreate
from app.services import agent_service, answer_presentation, chat_service


fba = answer_presentation.format_business_answer


def _bullet_lines(result: str) -> list[str]:
    return [line for line in result.split("\n") if line.startswith("•")]


class TestEmptyAndScalar:
    def test_empty_result(self):
        assert fba([]) == "No matching results were found."

    def test_single_scalar_count(self):
        assert fba([{"total_employees": 420}]) == "Total employees: 420."

    def test_single_scalar_bare_total_is_not_treated_as_currency(self):
        # "total_orders" contains "total" but not a currency-specific keyword — a plain count.
        assert fba([{"total_orders": 420}]) == "Total orders: 420."

    def test_single_scalar_decimal_rating(self):
        assert fba([{"average_rating": 4.1375}]) == "Average rating: 4.14."

    def test_single_row_multi_metric_stays_a_sentence_not_bullets(self):
        # A single row is one entity/aggregate, not "multiple pieces of information" — no
        # bullets even though it has more than one field.
        result = fba([{"avg_salary": 95000, "headcount": 12}])
        assert result == "Avg salary: $95,000, Headcount: 12."
        assert "•" not in result

    def test_single_row_ignores_id_columns(self):
        result = fba([{"employee_id": 7, "total_net_salary": 12500.5}])
        assert "employee_id" not in result.lower()
        assert "7" not in result  # the id value itself must never appear — it was excluded entirely
        assert "Total net salary" in result


class TestGroupedFewRows:
    """Real shape: status/payment-method breakdowns — 1 label column, 1 metric column, a
    handful of rows. Multi-row results must render as bullets, never one paragraph."""

    def test_order_status_revenue_breakdown(self):
        rows = [
            {"status": "Completed", "total_revenue": 30152100},
            {"status": "Cancelled", "total_revenue": 6079000},
            {"status": "Pending", "total_revenue": 5654000},
        ]
        result = fba(rows)
        assert result.startswith("Highest total revenue:")
        bullets = _bullet_lines(result)
        assert bullets == [
            "• Completed — $30.15M",
            "• Cancelled — $6.08M",
            "• Pending — $5.65M",
        ]
        assert "|" not in result and "##" not in result and "**" not in result
        # Never a single dense paragraph concatenating all rows.
        assert result.count("\n") >= 2

    def test_payment_method_breakdown_real_values(self):
        rows = [
            {"payment_method": "Credit Card", "total_amount": 8670000},
            {"payment_method": "Direct Debit", "total_amount": 8060000},
            {"payment_method": "Cash", "total_amount": 7000000},
            {"payment_method": "Bank Transfer", "total_amount": 6630000},
        ]
        result = fba(rows)
        bullets = _bullet_lines(result)
        assert bullets == [
            "• Credit Card — $8.67M",
            "• Direct Debit — $8.06M",
            "• Cash — $7.00M",
            "• Bank Transfer — $6.63M",
        ]

    def test_not_sorted_uses_neutral_intro_not_leading_claim(self):
        # Same values as above but shuffled — must NOT claim any status "leads" since the data
        # as given doesn't demonstrate that ordering.
        rows = [
            {"status": "Pending", "total_revenue": 5654000},
            {"status": "Completed", "total_revenue": 30152100},
            {"status": "Cancelled", "total_revenue": 6079000},
        ]
        result = fba(rows)
        assert "Highest" not in result
        assert result.startswith("Total revenue by status:")
        assert "• Pending — $5.65M" in result


class TestRanking:
    """Real shape: sales-rep ranking — first_name/last_name/region + 1 metric, 10 rows."""

    ROWS = [
        {"first_name": "Karim", "last_name": "Nabil", "region": "West", "total_sales": 5174800},
        {"first_name": "Nour", "last_name": "Adel", "region": "East", "total_sales": 4934100},
        {"first_name": "Mariam", "last_name": "Sayed", "region": "North", "total_sales": 4602200},
        {"first_name": "Adam", "last_name": "Samir", "region": "South", "total_sales": 4485100},
        {"first_name": "Omar", "last_name": "Ali", "region": "South", "total_sales": 4465200},
        {"first_name": "Hana", "last_name": "Mostafa", "region": "North", "total_sales": 4289900},
        {"first_name": "Lina", "last_name": "Hassan", "region": "North", "total_sales": 4095500},
        {"first_name": "Sara", "last_name": "Mahmoud", "region": "East", "total_sales": 3908300},
        {"first_name": "Tarek", "last_name": "Kamel", "region": "West", "total_sales": 3529600},
        {"first_name": "Youssef", "last_name": "Fathy", "region": "South", "total_sales": 2400400},
    ]

    def test_merges_first_and_last_name_and_renders_bullets(self):
        result = fba(self.ROWS)
        assert result.startswith("Highest total sales:")
        bullets = _bullet_lines(result)
        assert bullets[0] == "• Karim Nabil — $5.17M"
        assert len(bullets) == 5  # capped, never one bullet per row for a 10-row result

    def test_caps_at_five_named_items_and_states_true_range(self):
        result = fba(self.ROWS)
        # Only the top 5 are named by identity...
        assert "Youssef Fathy" not in result
        # ...but the true total count and true min/max (computed over ALL 10 rows) are stated.
        assert "10 results total" in result
        assert "$5.17M" in result  # max
        assert "$2.40M" in result  # min — real value (2,400,400), not invented
        assert "View data for the full breakdown" in result

    def test_region_dropped_from_bullets_but_not_hallucinated(self):
        result = fba(self.ROWS)
        # region is a 4th column beyond the merged name pair — one "extra" label is tolerated
        # (still ranks), but it's dropped from the bullet text for concision.
        assert "West" not in result and "East" not in result

    def test_never_lists_more_than_five_bullets(self):
        result = fba(self.ROWS)
        assert len(_bullet_lines(result)) == 5


class TestMultiMetricGrouped:
    def test_category_avg_price_and_count_renders_labeled_bullets(self):
        # Real captured shape (7 categories) — active_product_count genuinely varies (1 or 2)
        # here, unlike a smaller sample that might coincidentally all share one value.
        rows = [
            {"category": "Software", "average_unit_price": 12750.0, "active_product_count": 2},
            {"category": "Data Engineering", "average_unit_price": 11850.0, "active_product_count": 2},
            {"category": "Analytics", "average_unit_price": 10350.0, "active_product_count": 2},
            {"category": "Security", "average_unit_price": 9800.0, "active_product_count": 1},
            {"category": "Infrastructure", "average_unit_price": 5450.0, "active_product_count": 2},
            {"category": "Integration", "average_unit_price": 4900.0, "active_product_count": 2},
            {"category": "Services", "average_unit_price": 3000.0, "active_product_count": 1},
        ]
        result = fba(rows)
        bullets = _bullet_lines(result)
        assert bullets[0] == "• Software — Average unit price: $12,750 · Active product count: 2"
        assert len(bullets) == 5  # capped like any other multi-row result
        assert "View data for the full breakdown" in result

    def test_constant_second_metric_pulled_out_as_a_shared_fact(self):
        rows = [
            {"category": "Software", "average_unit_price": 12750.0, "active_product_count": 2},
            {"category": "Data Engineering", "average_unit_price": 11850.0, "active_product_count": 2},
            {"category": "Analytics", "average_unit_price": 10350.0, "active_product_count": 2},
        ]
        result = fba(rows)
        assert result.startswith("Active product count: 2.")
        bullets = _bullet_lines(result)
        # Bullets use only the varying metric — the constant is never repeated per item.
        assert bullets[0] == "• Software — $12,750"
        assert "Active product count: 2, Active product count: 2" not in result


class TestConstantMetricSeparation:
    """Real shape: 43 customers who all bought the same product, so unit_price is identical
    on every row while total_spent varies — a real live bug where the constant metric got
    repeated on every item and wrongly drove a "ranging from $18,000 to $18,000" statement
    that should have been based on the actually-varying total_spent instead."""

    ROWS = [
        {"customer_name": "Customer 12", "unit_price": 18000, "total_spent": 540000},
        {"customer_name": "Customer 20", "unit_price": 18000, "total_spent": 468000},
        {"customer_name": "Customer 56", "unit_price": 18000, "total_spent": 450000},
        {"customer_name": "Customer 21", "unit_price": 18000, "total_spent": 396000},
        {"customer_name": "Customer 36", "unit_price": 18000, "total_spent": 360000},
        {"customer_name": "Customer 46", "unit_price": 18000, "total_spent": 18000},
    ]

    def test_constant_metric_stated_once_not_per_item(self):
        result = fba(self.ROWS)
        assert result.startswith("Unit price: $18,000.")
        assert result.count("$18,000") == 2  # once as the shared fact, once as the min in range
        bullets = _bullet_lines(result)
        assert bullets[0] == "• Customer 12 — $540,000"

    def test_range_uses_the_varying_metric_not_the_constant_one(self):
        result = fba(self.ROWS)
        assert "ranging from $18,000 to $540,000" in result
        assert "ranging from $18,000 to $18,000" not in result

    def test_leader_identified_by_the_varying_metric(self):
        result = fba(self.ROWS)
        assert "Highest total spent:" in result
        assert "• Customer 12 — $540,000" in result


class TestListedNoMetric:
    """Real shape: department/manager listing — 4 label columns, zero metric columns."""

    def test_department_manager_listing_renders_bullets(self):
        rows = [
            {"department_name": "Engineering", "company_name": "Nexa Technologies", "first_name": "Sara", "last_name": "Mostafa"},
            {"department_name": "Human Resources", "company_name": "Nexa Technologies", "first_name": "Jana", "last_name": "Younis"},
            {"department_name": "Finance", "company_name": "Nexa Technologies", "first_name": "Karim", "last_name": "Hamdy"},
            {"department_name": "Sales", "company_name": "Nexa Technologies", "first_name": "Dina", "last_name": "Rashad"},
            {"department_name": "Marketing", "company_name": "Nexa Technologies", "first_name": "Lina", "last_name": "Ali"},
            {"department_name": "Operations", "company_name": "Nexa Technologies", "first_name": "Ziad", "last_name": "Fathy"},
            {"department_name": "Customer Success", "company_name": "Nexa Technologies", "first_name": "Sara", "last_name": "Mostafa"},
            {"department_name": "Data & Analytics", "company_name": "Nexa Technologies", "first_name": "Mohamed", "last_name": "Kamel"},
        ]
        result = fba(rows)
        assert result.startswith("8 departments found:")
        bullets = _bullet_lines(result)
        assert bullets[0] == "• Engineering (Sara Mostafa)"
        assert len(bullets) == 8
        assert "Data & Analytics" in result
        assert "|" not in result and "##" not in result


class TestAmbiguousIdentityFallback:
    """Real shape: 131-row employee/project/role assignments — this is exactly why a fixed
    'always rank by the metric' rule would misrepresent the data (naming just the employee
    while silently dropping which project and role would be wrong, not just imprecise). No
    bullets here either — there's no safe single identity to put on a bullet line."""

    def test_many_label_columns_with_a_metric_falls_back_honestly(self):
        rows = [
            {
                "employee_id": i, "first_name": "X", "last_name": "Y", "job_title": "T",
                "project_id": i % 6, "project_name": f"Project {i % 6}", "budget": 100000.0, "role": "R",
            }
            for i in range(131)
        ]
        result = answer_presentation.format_business_answer(rows)
        assert result == "131 results found. View data for the full breakdown."
        assert "•" not in result
        # Must not claim a specific person/project "leads" — the shape is too multi-dimensional
        # for that to be a faithful summary.
        assert "leads" not in result and "Highest" not in result

    def test_pure_metrics_no_label_reports_count_only(self):
        rows = [{"total_amount": 100}, {"total_amount": 200}, {"total_amount": 50}]
        # No label column at all (unusual, but must degrade honestly rather than crash).
        result = fba(rows)
        assert result == "3 results found. View data for details."
        assert "•" not in result


class TestNumberFormatting:
    def test_currency_under_a_million_uses_commas(self):
        assert answer_presentation._format_currency(540000) == "$540,000"

    def test_currency_over_a_million_abbreviates(self):
        assert answer_presentation._format_currency(30152100) == "$30.15M"

    def test_currency_negative(self):
        assert answer_presentation._format_currency(-500) == "-$500"

    def test_plain_integer(self):
        assert answer_presentation._format_number(420) == "420"

    def test_plain_decimal_rounds_to_two_places(self):
        assert answer_presentation._format_number(4.1375) == "4.14"

    def test_currency_keyword_matches_specific_terms_not_bare_total(self):
        assert answer_presentation._is_currency_column("total_revenue") is True
        assert answer_presentation._is_currency_column("unit_price") is True
        assert answer_presentation._is_currency_column("avg_salary") is True
        assert answer_presentation._is_currency_column("total_orders") is False
        assert answer_presentation._is_currency_column("headcount") is False

    def test_date_like_column_never_misclassified_as_currency(self):
        # target_month contains "target" (a currency keyword) but holds a date string — value
        # type must gate this before the keyword ever gets checked.
        labels, metrics, dates = answer_presentation._classify_columns(
            {"target_month": "2024-03-01", "target_amount": 50000.0}
        )
        assert "target_month" in dates
        assert "target_amount" in metrics


class TestSendMessageIntegration:
    """The full chat_service.send_message flow: content is deterministic (no LLM call for
    presentation), raw_answer still preserved, and normalization is now instant."""

    def test_grouped_question_produces_clean_deterministic_content(self, app_db, company, user, hr_demo_db_path):
        out = agent_service.create_agent(
            app_db, company_id=company.id, owner_id=user.id, payload=AgentCreate(name="Presentation Test Agent")
        )
        from app.models.agent import Agent

        agent = app_db.get(Agent, out.id)
        database_connection_repository.upsert(
            app_db, agent_id=agent.id, dialect="sqlite", host=None, port=None, database_name=None,
            username=None, encrypted_password=None, sqlite_file_path=hr_demo_db_path,
        )
        agent.knowledge_version += 1
        app_db.commit()

        conversation = conversation_repository.create(app_db, agent_id=agent.id, user_id=agent.owner_id)
        app_db.commit()

        start = time.monotonic()
        message = chat_service.send_message(app_db, agent, conversation, "How many employees are there?")
        elapsed = time.monotonic() - start

        if message.error_message:
            pytest.skip(f"Live model call did not succeed this run: {message.error_message}")

        assert "|" not in message.content
        assert "##" not in message.content
        assert "**" not in message.content
        assert "here are the results" not in message.content.lower()
        # No second LLM round-trip for presentation — the whole reply (agent SQL generation +
        # deterministic formatting) should complete well under what a second model call alone
        # used to add on top.
        assert elapsed < 60, f"Unexpectedly slow for a single-agent-call round trip: {elapsed:.1f}s"
