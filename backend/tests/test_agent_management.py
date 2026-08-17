"""Agent management: create, rename, delete — isolation, cascade cleanup, engine-cache
invalidation, and legacy-record backward compatibility. Uses an isolated test database
(app_db fixture) — never touches the real dev database or the real agents A/B/C.
"""
from __future__ import annotations

from app.integrations import text2sql_adapter
from app.models.agent import Agent
from app.repositories import (
    agent_repository,
    conversation_repository,
    database_connection_repository,
    knowledge_asset_repository,
    message_repository,
)
from app.schemas.agent import AgentCreate, AgentUpdate
from app.services import agent_service


def _make_agent(app_db, company, user, name="Test Agent") -> Agent:
    out = agent_service.create_agent(
        app_db, company_id=company.id, owner_id=user.id, payload=AgentCreate(name=name)
    )
    return app_db.get(Agent, out.id)


class TestCreateAgent:
    def test_create_agent_produces_independent_id_and_empty_state(self, app_db, company, user):
        agent_a = _make_agent(app_db, company, user, name="Agent A")
        agent_b = _make_agent(app_db, company, user, name="Agent B")

        assert agent_a.id != agent_b.id
        assert database_connection_repository.get_by_agent(app_db, agent_a.id) is None
        assert database_connection_repository.get_by_agent(app_db, agent_b.id) is None
        assert knowledge_asset_repository.list_by_agent(app_db, agent_a.id) == []
        assert knowledge_asset_repository.list_by_agent(app_db, agent_b.id) == []
        assert agent_a.status == "draft"
        assert agent_a.knowledge_version == 0

    def test_creating_agent_b_does_not_affect_agent_a(self, app_db, company, user):
        agent_a = _make_agent(app_db, company, user, name="Agent A")
        database_connection_repository.upsert(
            app_db, agent_id=agent_a.id, dialect="sqlite", host=None, port=None,
            database_name=None, username=None, encrypted_password=None,
            sqlite_file_path="C:/fake/a.db",
        )
        app_db.commit()

        before = database_connection_repository.get_by_agent(app_db, agent_a.id)
        assert before is not None

        _make_agent(app_db, company, user, name="Agent B")

        after = database_connection_repository.get_by_agent(app_db, agent_a.id)
        assert after is not None
        assert after.sqlite_file_path == "C:/fake/a.db"


class TestRenameAgent:
    def test_rename_changes_only_name_preserves_everything_else(self, app_db, company, user):
        agent = _make_agent(app_db, company, user, name="HR Analytics")
        conn = database_connection_repository.upsert(
            app_db, agent_id=agent.id, dialect="sqlite", host=None, port=None,
            database_name=None, username=None, encrypted_password=None,
            sqlite_file_path="C:/fake/hr.db",
        )
        app_db.commit()

        original_id = agent.id
        original_knowledge_version = agent.knowledge_version
        original_conn_id = conn.id

        updated = agent_service.update_agent(app_db, agent, AgentUpdate(name="HR Analytics Demo"))

        assert updated.name == "HR Analytics Demo"
        assert updated.id == original_id
        assert updated.knowledge_version == original_knowledge_version

        conn_after = database_connection_repository.get_by_agent(app_db, original_id)
        assert conn_after.id == original_conn_id
        assert conn_after.sqlite_file_path == "C:/fake/hr.db"

    def test_rename_invalidates_engine_cache_for_that_agent_only(self, app_db, company, user, hr_demo_connection_string):
        agent_x = _make_agent(app_db, company, user, name="Agent X")
        agent_y = _make_agent(app_db, company, user, name="Agent Y")
        text2sql_adapter.invalidate_engine(agent_x.id)
        text2sql_adapter.invalidate_engine(agent_y.id)

        engine_x1 = text2sql_adapter.get_engine(
            agent_id=agent_x.id, knowledge_version=0, llm_model="openai:test-model",
            connection_string=hr_demo_connection_string,
        )
        engine_y1 = text2sql_adapter.get_engine(
            agent_id=agent_y.id, knowledge_version=0, llm_model="openai:test-model",
            connection_string=hr_demo_connection_string,
        )

        agent_service.update_agent(app_db, agent_x, AgentUpdate(name="Agent X Renamed"))

        engine_x2 = text2sql_adapter.get_engine(
            agent_id=agent_x.id, knowledge_version=0, llm_model="openai:test-model",
            connection_string=hr_demo_connection_string,
        )
        engine_y2 = text2sql_adapter.get_engine(
            agent_id=agent_y.id, knowledge_version=0, llm_model="openai:test-model",
            connection_string=hr_demo_connection_string,
        )

        assert engine_x2 is not engine_x1, "Agent X's engine must be rebuilt after its update"
        assert engine_y2 is engine_y1, "Agent Y's engine must be untouched by Agent X's rename"

        text2sql_adapter.invalidate_engine(agent_x.id)
        text2sql_adapter.invalidate_engine(agent_y.id)


class TestDeleteAgent:
    def _populate_related_data(self, app_db, agent):
        database_connection_repository.upsert(
            app_db, agent_id=agent.id, dialect="sqlite", host=None, port=None,
            database_name=None, username=None, encrypted_password=None,
            sqlite_file_path="C:/fake/del.db",
        )
        knowledge_asset_repository.upsert(
            app_db, agent_id=agent.id, asset_type="schema", source="generated", status="ready",
            content="{}", verified=True,
        )
        conversation = conversation_repository.create(app_db, agent_id=agent.id, user_id=agent.owner_id)
        message_repository.create(app_db, conversation_id=conversation.id, role="user", content="hi")
        app_db.commit()
        return conversation.id

    def test_delete_removes_all_related_records_no_orphans(self, app_db, company, user):
        agent = _make_agent(app_db, company, user, name="Disposable Agent")
        agent_id = agent.id
        conversation_id = self._populate_related_data(app_db, agent)

        agent_service.delete_agent(app_db, agent)

        assert agent_repository.list_agents_for_company(app_db, company.id) == [] or all(
            a.id != agent_id for a in agent_repository.list_agents_for_company(app_db, company.id)
        )
        assert database_connection_repository.get_by_agent(app_db, agent_id) is None
        assert knowledge_asset_repository.list_by_agent(app_db, agent_id) == []
        assert conversation_repository.get(app_db, conversation_id) is None
        assert message_repository.list_by_conversation(app_db, conversation_id) == []

    def test_deleting_one_agent_does_not_affect_another(self, app_db, company, user):
        agent_keep = _make_agent(app_db, company, user, name="Keep Me")
        agent_delete = _make_agent(app_db, company, user, name="Delete Me")

        self._populate_related_data(app_db, agent_keep)
        conv_delete_id = self._populate_related_data(app_db, agent_delete)

        agent_service.delete_agent(app_db, agent_delete)

        # The deleted agent's data is gone...
        assert database_connection_repository.get_by_agent(app_db, agent_delete.id) is None
        assert conversation_repository.get(app_db, conv_delete_id) is None
        # ...but the surviving agent's data is completely intact.
        kept_conn = database_connection_repository.get_by_agent(app_db, agent_keep.id)
        assert kept_conn is not None
        assert kept_conn.sqlite_file_path == "C:/fake/del.db"
        assert len(knowledge_asset_repository.list_by_agent(app_db, agent_keep.id)) == 1
        remaining = agent_repository.list_agents_for_company(app_db, company.id)
        assert len(remaining) == 1
        assert remaining[0].id == agent_keep.id

    def test_delete_invalidates_engine_cache_only_for_that_agent(
        self, app_db, company, user, hr_demo_connection_string, ecommerce_demo_connection_string
    ):
        agent_keep = _make_agent(app_db, company, user, name="Keep Engine")
        agent_delete = _make_agent(app_db, company, user, name="Delete Engine")
        text2sql_adapter.invalidate_engine(agent_keep.id)
        text2sql_adapter.invalidate_engine(agent_delete.id)

        engine_keep = text2sql_adapter.get_engine(
            agent_id=agent_keep.id, knowledge_version=0, llm_model="openai:test-model",
            connection_string=hr_demo_connection_string,
        )
        engine_delete = text2sql_adapter.get_engine(
            agent_id=agent_delete.id, knowledge_version=0, llm_model="openai:test-model",
            connection_string=ecommerce_demo_connection_string,
        )

        agent_service.delete_agent(app_db, agent_delete)

        # Requesting the deleted agent's old cache key again must rebuild, not reuse.
        engine_delete_again = text2sql_adapter.get_engine(
            agent_id=agent_delete.id, knowledge_version=0, llm_model="openai:test-model",
            connection_string=ecommerce_demo_connection_string,
        )
        engine_keep_again = text2sql_adapter.get_engine(
            agent_id=agent_keep.id, knowledge_version=0, llm_model="openai:test-model",
            connection_string=hr_demo_connection_string,
        )

        assert engine_delete_again is not engine_delete
        assert engine_keep_again is engine_keep, "Deleting one agent must not evict another agent's engine"

        text2sql_adapter.invalidate_engine(agent_keep.id)
        text2sql_adapter.invalidate_engine(agent_delete.id)


class TestLegacyAgentCompatibility:
    def test_legacy_knowledge_asset_missing_verified_flag_loads_with_safe_default(self, app_db, company, user):
        """Simulates a KnowledgeAsset row created before the `verified` column existed —
        it must load fine and report verified=False, never crash and never claim
        verification it never underwent."""
        agent = _make_agent(app_db, company, user, name="Legacy Agent")
        # Pre-upgrade generate_documentation_asset never passed verified= at all.
        asset = knowledge_asset_repository.upsert(
            app_db,
            agent_id=agent.id,
            asset_type="documentation",
            source="generated",
            status="ready",
            content="# Old doc\nNo grounding checks ran when this was written.",
        )
        app_db.commit()

        from app.schemas.knowledge_asset import KnowledgeAssetOut

        out = KnowledgeAssetOut.model_validate(asset)
        assert out.status == "ready"
        assert out.source == "generated"
        assert out.verified is False, "Legacy content must never claim it passed verification it never ran through"
        assert out.content == "# Old doc\nNo grounding checks ran when this was written."

    def test_legacy_agent_can_still_be_loaded_and_enriched(self, app_db, company, user):
        agent = _make_agent(app_db, company, user, name="Old Agent")
        # No database connection, no knowledge assets — the state a legacy agent might be in.
        detail = agent_service.get_agent_detail(app_db, agent)
        assert detail.id == agent.id
        assert detail.database_connected is False
        assert detail.knowledge_ready_count == 0
        assert detail.knowledge_total_count == 3
