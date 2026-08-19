"""Agent Memory / Business Rules: CRUD, validation, agent isolation, and — the most
important part — that a saved rule actually reaches the shared TextSQL engine-construction
seam (chat_service.resolve_engine_for_agent) used by both Chat and the Validation Workspace.

Engine-construction tests build the real TextSQL engine (real schema introspection against
the real HR demo sqlite database) but never call .ask()/.stream_ask() — so they need no LLM
network access and are fully deterministic, matching this repo's "no mocks" convention while
staying reliable.
"""
from __future__ import annotations

import inspect

from app.integrations import text2sql_adapter
from app.models.agent import Agent
from app.repositories import agent_memory_repository, database_connection_repository
from app.schemas.agent import AgentCreate
from app.security import create_access_token
from app.services import agent_service, chat_service, validation_service


def auth_headers(user) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


# ── CRUD (HTTP, real authorization boundary) ────────────────────────────────────────────


def test_owner_can_create_list_and_delete_a_business_rule(client, scenario):
    agent_id = scenario["agent"].id
    headers = auth_headers(scenario["owner"])

    assert client.get(f"/api/agents/{agent_id}/memory", headers=headers).json() == []

    create_resp = client.post(
        f"/api/agents/{agent_id}/memory", json={"content": "Revenue excludes cancelled orders."}, headers=headers
    )
    assert create_resp.status_code == 200
    rule = create_resp.json()
    assert rule["content"] == "Revenue excludes cancelled orders."
    assert rule["agent_id"] == agent_id

    list_resp = client.get(f"/api/agents/{agent_id}/memory", headers=headers)
    assert list_resp.status_code == 200
    assert [r["id"] for r in list_resp.json()] == [rule["id"]]

    delete_resp = client.delete(f"/api/agents/{agent_id}/memory/{rule['id']}", headers=headers)
    assert delete_resp.status_code == 200
    assert client.get(f"/api/agents/{agent_id}/memory", headers=headers).json() == []


def test_admin_can_manage_business_rules(client, scenario):
    agent_id = scenario["agent"].id
    resp = client.post(
        f"/api/agents/{agent_id}/memory", json={"content": "Fiscal year starts July 1."},
        headers=auth_headers(scenario["admin"]),
    )
    assert resp.status_code == 200


def test_shared_user_can_read_but_not_create_or_delete_business_rules(client, scenario):
    agent_id = scenario["agent"].id
    owner, shared_user = scenario["owner"], scenario["shared_user"]
    client.post(
        f"/api/agents/{agent_id}/shares", json={"user_id": shared_user.id, "role": "viewer"}, headers=auth_headers(owner)
    )
    rule = client.post(
        f"/api/agents/{agent_id}/memory", json={"content": "Active employees have status = Active."},
        headers=auth_headers(owner),
    ).json()

    headers = auth_headers(shared_user)
    assert client.get(f"/api/agents/{agent_id}/memory", headers=headers).status_code == 200
    assert client.post(
        f"/api/agents/{agent_id}/memory", json={"content": "hack"}, headers=headers
    ).status_code == 403
    assert client.delete(f"/api/agents/{agent_id}/memory/{rule['id']}", headers=headers).status_code == 403


def test_empty_or_whitespace_content_is_rejected(client, scenario):
    agent_id = scenario["agent"].id
    headers = auth_headers(scenario["owner"])
    assert client.post(f"/api/agents/{agent_id}/memory", json={"content": ""}, headers=headers).status_code == 422
    assert client.post(f"/api/agents/{agent_id}/memory", json={"content": "   "}, headers=headers).status_code == 422


def test_content_is_trimmed(client, scenario):
    agent_id = scenario["agent"].id
    resp = client.post(
        f"/api/agents/{agent_id}/memory", json={"content": "  Revenue excludes cancelled orders.  "},
        headers=auth_headers(scenario["owner"]),
    )
    assert resp.json()["content"] == "Revenue excludes cancelled orders."


# ── Isolation ────────────────────────────────────────────────────────────────────────────


def test_agent_a_memory_is_invisible_to_agent_b_and_cross_agent_delete_is_rejected(client, scenario):
    owner = scenario["owner"]
    agent_a_id = scenario["agent"].id
    agent_b_id = scenario["draft_agent"].id  # a second, distinct agent owned by the same owner

    rule_a = client.post(
        f"/api/agents/{agent_a_id}/memory", json={"content": "Agent A's rule."}, headers=auth_headers(owner)
    ).json()
    client.post(f"/api/agents/{agent_b_id}/memory", json={"content": "Agent B's rule."}, headers=auth_headers(owner))

    agent_b_rules = client.get(f"/api/agents/{agent_b_id}/memory", headers=auth_headers(owner)).json()
    assert all(r["content"] != "Agent A's rule." for r in agent_b_rules), "Agent B must never see Agent A's memory"

    # Deleting agent A's rule through agent B's URL must not find it.
    cross_delete = client.delete(f"/api/agents/{agent_b_id}/memory/{rule_a['id']}", headers=auth_headers(owner))
    assert cross_delete.status_code == 404

    # It's still there, untouched, under its real agent.
    agent_a_rules = client.get(f"/api/agents/{agent_a_id}/memory", headers=auth_headers(owner)).json()
    assert any(r["id"] == rule_a["id"] for r in agent_a_rules)


def test_cross_company_user_cannot_read_or_write_memory(client, scenario):
    agent_id = scenario["agent"].id
    headers = auth_headers(scenario["company_b_user"])
    assert client.get(f"/api/agents/{agent_id}/memory", headers=headers).status_code == 404
    assert client.post(
        f"/api/agents/{agent_id}/memory", json={"content": "hack"}, headers=headers
    ).status_code == 404


# ── combine_instructions (pure unit tests) ──────────────────────────────────────────────


def test_no_memories_and_no_custom_instructions_preserves_prior_behavior():
    assert text2sql_adapter.combine_instructions(None, []) is None
    assert text2sql_adapter.combine_instructions("", []) is None


def test_no_memories_returns_custom_instructions_unchanged():
    assert text2sql_adapter.combine_instructions("Be concise.", []) == "Be concise."


def test_memories_without_custom_instructions_are_still_included():
    result = text2sql_adapter.combine_instructions(None, ["Revenue excludes cancelled orders."])
    assert result is not None
    assert "Revenue excludes cancelled orders." in result


def test_multiple_memories_are_all_included_and_custom_instructions_preserved():
    result = text2sql_adapter.combine_instructions(
        "Be concise.",
        ["Revenue excludes cancelled orders.", "Fiscal year starts July 1.", "  ", ""],
    )
    assert "Be concise." in result
    assert "Revenue excludes cancelled orders." in result
    assert "Fiscal year starts July 1." in result
    # Blank/whitespace-only entries must not produce empty bullet lines.
    assert "\n- \n" not in result
    assert not result.rstrip().endswith("-")


def test_memory_framing_treats_rules_as_guidance_not_authoritative_schema():
    """The prompt language itself must tell the model: apply when relevant, never invent
    schema, never fabricate a workaround — this is what's actually testable deterministically
    about "memory should guide, not override, and never fabricate" (the model's live
    compliance is inherently non-deterministic and out of scope for a unit test)."""
    result = text2sql_adapter.combine_instructions(None, ["Revenue excludes cancelled orders."])
    assert "relevant" in result
    assert "ignore" in result
    assert "invent" in result
    assert "schema" in result


# ── Real engine construction — the actual Chat/Validation integration ──────────────────


def _make_connected_agent(app_db, company, user, hr_demo_db_path, name="Memory Test Agent") -> Agent:
    out = agent_service.create_agent(app_db, company_id=company.id, owner_id=user.id, payload=AgentCreate(name=name))
    agent = app_db.get(Agent, out.id)
    database_connection_repository.upsert(
        app_db, agent_id=agent.id, dialect="sqlite", host=None, port=None, database_name=None,
        username=None, encrypted_password=None, sqlite_file_path=hr_demo_db_path,
    )
    agent.knowledge_version += 1
    app_db.commit()
    return agent


def test_agents_business_rule_reaches_the_real_textsql_engine_instructions(app_db, company, user, hr_demo_db_path):
    """This is chat_service.resolve_engine_for_agent — the exact function Chat's
    send_message/stream_message call. Building the engine performs real schema
    introspection but never calls the LLM, so this is a real (non-mocked), deterministic
    check that the rule actually reaches TextSQL, not just that our own code "looks right"."""
    agent = _make_connected_agent(app_db, company, user, hr_demo_db_path)
    agent_memory_repository.create(app_db, agent_id=agent.id, content="Revenue excludes cancelled orders.")
    app_db.commit()

    engine = chat_service.resolve_engine_for_agent(app_db, agent)
    try:
        assert "Revenue excludes cancelled orders." in engine.generator.instructions
    finally:
        text2sql_adapter.invalidate_engine(agent.id)


def test_agent_with_no_business_rules_has_unchanged_instructions(app_db, company, user, hr_demo_db_path):
    """An agent with zero memories must behave exactly as before Agent Memory existed."""
    agent = _make_connected_agent(app_db, company, user, hr_demo_db_path, name="No Rules Agent")
    assert agent_memory_repository.list_by_agent(app_db, agent.id) == []

    engine = chat_service.resolve_engine_for_agent(app_db, agent)
    try:
        assert engine.generator.instructions == agent.custom_instructions  # both None here
    finally:
        text2sql_adapter.invalidate_engine(agent.id)


def test_multiple_business_rules_all_reach_the_engine(app_db, company, user, hr_demo_db_path):
    agent = _make_connected_agent(app_db, company, user, hr_demo_db_path, name="Multi Rule Agent")
    agent_memory_repository.create(app_db, agent_id=agent.id, content="Revenue excludes cancelled orders.")
    agent_memory_repository.create(app_db, agent_id=agent.id, content="Fiscal year starts July 1.")
    app_db.commit()

    engine = chat_service.resolve_engine_for_agent(app_db, agent)
    try:
        assert "Revenue excludes cancelled orders." in engine.generator.instructions
        assert "Fiscal year starts July 1." in engine.generator.instructions
    finally:
        text2sql_adapter.invalidate_engine(agent.id)


def test_agent_a_memory_never_reaches_agent_b_engine(app_db, company, user, hr_demo_db_path):
    agent_a = _make_connected_agent(app_db, company, user, hr_demo_db_path, name="Engine Agent A")
    agent_b = _make_connected_agent(app_db, company, user, hr_demo_db_path, name="Engine Agent B")
    agent_memory_repository.create(app_db, agent_id=agent_a.id, content="Only Agent A knows this rule.")
    app_db.commit()

    engine_b = chat_service.resolve_engine_for_agent(app_db, agent_b)
    try:
        instructions_b = engine_b.generator.instructions or ""
        assert "Only Agent A knows this rule." not in instructions_b
    finally:
        text2sql_adapter.invalidate_engine(agent_a.id)
        text2sql_adapter.invalidate_engine(agent_b.id)


def test_saving_a_new_rule_invalidates_the_cached_engine_so_it_actually_applies(
    app_db, company, user, hr_demo_db_path
):
    """The engine cache is keyed on (agent_id, knowledge_version), which a business rule
    doesn't bump — without an explicit invalidation, a rule saved after the engine was first
    built would silently never take effect. This proves create/delete evict the cache."""
    from app.services import agent_memory_service

    agent = _make_connected_agent(app_db, company, user, hr_demo_db_path, name="Cache Invalidation Agent")

    engine_before = chat_service.resolve_engine_for_agent(app_db, agent)
    assert not engine_before.generator.instructions

    memory = agent_memory_service.create_memory(app_db, agent.id, "Revenue excludes cancelled orders.")

    engine_after = chat_service.resolve_engine_for_agent(app_db, agent)
    assert engine_after is not engine_before, "a new engine must be built after a rule is saved"
    assert "Revenue excludes cancelled orders." in engine_after.generator.instructions

    agent_memory_service.delete_memory(app_db, memory)
    engine_after_delete = chat_service.resolve_engine_for_agent(app_db, agent)
    assert engine_after_delete is not engine_after
    assert not engine_after_delete.generator.instructions

    text2sql_adapter.invalidate_engine(agent.id)


def test_validation_workspace_uses_the_same_shared_engine_path_as_chat():
    """Structural proof (same technique test_validation.py already uses for its own
    regression guards — see test_no_hardcoded_row_comparison_shortcut_in_run_test) that
    validation_service builds its engine via chat_service.resolve_engine_for_agent, the
    exact function proven above to embed Agent Memory — not a second, parallel path that
    could silently diverge and skip business rules."""
    source = inspect.getsource(validation_service.run_test)
    assert "resolve_engine_for_agent" in source
