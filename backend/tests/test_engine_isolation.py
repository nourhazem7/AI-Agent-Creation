"""Proves agent isolation at the TextSQL-engine/cache level (not just the Knowledge Asset
level) — the exact property Milestone 6 requires: Agent A can never receive Agent B's
cached engine, database, or configuration.
"""
from __future__ import annotations

from app.config import get_settings
from app.integrations import text2sql_adapter

settings = get_settings()


def _clear_cache(*agent_ids: str) -> None:
    for agent_id in agent_ids:
        text2sql_adapter.invalidate_engine(agent_id)


class TestEngineCacheIsolation:
    def test_agent_a_and_agent_b_get_different_engines_for_different_databases(
        self, hr_demo_connection_string, ecommerce_demo_connection_string
    ):
        _clear_cache("test-agent-a", "test-agent-b")
        try:
            engine_a = text2sql_adapter.get_engine(
                agent_id="test-agent-a",
                knowledge_version=1,
                llm_model=settings.llm_model,
                connection_string=hr_demo_connection_string,
            )
            engine_b = text2sql_adapter.get_engine(
                agent_id="test-agent-b",
                knowledge_version=1,
                llm_model=settings.llm_model,
                connection_string=ecommerce_demo_connection_string,
            )

            assert engine_a is not engine_b
            # Not just different objects — actually wired to different real databases.
            assert engine_a.db.connection_string == hr_demo_connection_string
            assert engine_b.db.connection_string == ecommerce_demo_connection_string
            assert engine_a.db.connection_string != engine_b.db.connection_string
        finally:
            _clear_cache("test-agent-a", "test-agent-b")

    def test_requesting_agent_a_again_returns_engine_a_not_engine_b(
        self, hr_demo_connection_string, ecommerce_demo_connection_string
    ):
        """The exact scenario specified: Agent A + Database A -> Engine A, Agent B +
        Database B -> Engine B, then requesting Agent A again must return/reuse Engine A."""
        _clear_cache("test-agent-a", "test-agent-b")
        try:
            engine_a_first = text2sql_adapter.get_engine(
                agent_id="test-agent-a",
                knowledge_version=1,
                llm_model=settings.llm_model,
                connection_string=hr_demo_connection_string,
            )
            engine_b = text2sql_adapter.get_engine(
                agent_id="test-agent-b",
                knowledge_version=1,
                llm_model=settings.llm_model,
                connection_string=ecommerce_demo_connection_string,
            )
            engine_a_second = text2sql_adapter.get_engine(
                agent_id="test-agent-a",
                knowledge_version=1,
                llm_model=settings.llm_model,
                connection_string=hr_demo_connection_string,
            )

            assert engine_a_second is engine_a_first, "Requesting Agent A again must reuse Engine A"
            assert engine_a_second is not engine_b, "Agent A must never receive Agent B's engine"
        finally:
            _clear_cache("test-agent-a", "test-agent-b")

    def test_same_agent_same_knowledge_version_reuses_cached_engine(self, hr_demo_connection_string):
        _clear_cache("test-agent-cache")
        try:
            e1 = text2sql_adapter.get_engine(
                agent_id="test-agent-cache",
                knowledge_version=1,
                llm_model=settings.llm_model,
                connection_string=hr_demo_connection_string,
            )
            e2 = text2sql_adapter.get_engine(
                agent_id="test-agent-cache",
                knowledge_version=1,
                llm_model=settings.llm_model,
                connection_string=hr_demo_connection_string,
            )
            assert e1 is e2
        finally:
            _clear_cache("test-agent-cache")

    def test_knowledge_version_bump_forces_a_fresh_engine_for_the_same_agent(self, hr_demo_connection_string):
        _clear_cache("test-agent-version")
        try:
            e_v1 = text2sql_adapter.get_engine(
                agent_id="test-agent-version",
                knowledge_version=1,
                llm_model=settings.llm_model,
                connection_string=hr_demo_connection_string,
            )
            e_v2 = text2sql_adapter.get_engine(
                agent_id="test-agent-version",
                knowledge_version=2,
                llm_model=settings.llm_model,
                connection_string=hr_demo_connection_string,
            )
            assert e_v1 is not e_v2
        finally:
            _clear_cache("test-agent-version")

    def test_invalidate_engine_only_evicts_that_agent(
        self, hr_demo_connection_string, ecommerce_demo_connection_string
    ):
        _clear_cache("test-agent-p", "test-agent-q")
        try:
            e_p1 = text2sql_adapter.get_engine(
                agent_id="test-agent-p",
                knowledge_version=1,
                llm_model=settings.llm_model,
                connection_string=hr_demo_connection_string,
            )
            e_q1 = text2sql_adapter.get_engine(
                agent_id="test-agent-q",
                knowledge_version=1,
                llm_model=settings.llm_model,
                connection_string=ecommerce_demo_connection_string,
            )

            text2sql_adapter.invalidate_engine("test-agent-p")

            e_p2 = text2sql_adapter.get_engine(
                agent_id="test-agent-p",
                knowledge_version=1,
                llm_model=settings.llm_model,
                connection_string=hr_demo_connection_string,
            )
            e_q2 = text2sql_adapter.get_engine(
                agent_id="test-agent-q",
                knowledge_version=1,
                llm_model=settings.llm_model,
                connection_string=ecommerce_demo_connection_string,
            )

            assert e_p2 is not e_p1, "Agent P's engine must be rebuilt after invalidation"
            assert e_q2 is e_q1, "Agent Q's engine must be untouched by Agent P's invalidation"
        finally:
            _clear_cache("test-agent-p", "test-agent-q")
