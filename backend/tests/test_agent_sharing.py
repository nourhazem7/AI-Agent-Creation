from __future__ import annotations

from app.security import create_access_token


def auth_headers(user) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def _share(client, agent_id, owner, target_user_id, role="viewer"):
    return client.post(
        f"/api/agents/{agent_id}/shares",
        json={"user_id": target_user_id, "role": role},
        headers=auth_headers(owner),
    )


# ── Owner ──────────────────────────────────────────────────────────────────


def test_owner_has_full_control(client, scenario):
    agent_id = scenario["agent"].id
    owner = scenario["owner"]

    assert client.get(f"/api/agents/{agent_id}", headers=auth_headers(owner)).status_code == 200
    assert client.patch(
        f"/api/agents/{agent_id}", json={"description": "updated"}, headers=auth_headers(owner)
    ).status_code == 200
    assert client.get(f"/api/agents/{agent_id}/shares", headers=auth_headers(owner)).status_code == 200
    assert client.get(f"/api/agents/{agent_id}/database", headers=auth_headers(owner)).status_code == 404  # none configured yet, but authorized
    assert client.delete(f"/api/agents/{agent_id}", headers=auth_headers(owner)).status_code == 200


# ── Shared user (there is no editor/collaborate role — only use/read access) ────────────


def test_shared_user_can_access_but_not_modify(client, scenario):
    agent_id = scenario["agent"].id
    owner, shared_user = scenario["owner"], scenario["shared_user"]
    assert _share(client, agent_id, owner, shared_user.id).status_code == 200

    headers = auth_headers(shared_user)
    assert client.get(f"/api/agents/{agent_id}", headers=headers).status_code == 200
    assert client.get(f"/api/agents/{agent_id}/knowledge-assets", headers=headers).status_code == 200

    # Cannot modify the Agent itself.
    assert client.patch(f"/api/agents/{agent_id}", json={"description": "x"}, headers=headers).status_code == 403
    # Cannot modify Knowledge Assets.
    assert client.post(
        f"/api/agents/{agent_id}/knowledge-assets/schema/generate", headers=headers
    ).status_code == 403
    # Cannot modify validation/testcases.
    assert client.post(
        f"/api/agents/{agent_id}/validation-tests",
        json={"question": "How many rows?"},
        headers=headers,
    ).status_code == 403
    assert client.post(f"/api/agents/{agent_id}/validation-tests/run-all", headers=headers).status_code == 403
    # Cannot access the database connection.
    assert client.get(f"/api/agents/{agent_id}/database", headers=headers).status_code == 403
    # Cannot manage sharing.
    assert client.get(f"/api/agents/{agent_id}/shares", headers=headers).status_code == 403
    assert client.post(
        f"/api/agents/{agent_id}/shares", json={"user_id": scenario["outsider"].id, "role": "viewer"}, headers=headers
    ).status_code == 403
    # Cannot delete the Agent.
    assert client.delete(f"/api/agents/{agent_id}", headers=headers).status_code == 403


def test_shared_user_does_not_see_knowledge_error_message(client, scenario, db):
    from app.repositories import knowledge_asset_repository

    agent_id = scenario["agent"].id
    owner, shared_user = scenario["owner"], scenario["shared_user"]
    knowledge_asset_repository.upsert(
        db, agent_id=agent_id, asset_type="schema", source="generated", status="error",
        error_message="connection to host db.internal.company failed: password authentication failed",
    )
    db.commit()

    assert _share(client, agent_id, owner, shared_user.id).status_code == 200

    resp = client.get(f"/api/agents/{agent_id}/knowledge-assets/schema", headers=auth_headers(shared_user))
    assert resp.status_code == 200
    assert resp.json()["error_message"] is None

    owner_resp = client.get(f"/api/agents/{agent_id}/knowledge-assets/schema", headers=auth_headers(owner))
    assert owner_resp.status_code == 200
    assert "password authentication failed" in owner_resp.json()["error_message"]


def test_editor_role_no_longer_exists(client, scenario):
    """The product no longer has an editor/collaborate concept — a share can only ever be
    "viewer" (use/read access). Requesting "editor" must be rejected outright."""
    agent_id = scenario["agent"].id
    owner, target = scenario["owner"], scenario["shared_user"]
    resp = _share(client, agent_id, owner, target.id, "editor")
    assert resp.status_code == 422  # rejected at the schema boundary — "editor" isn't a valid ShareRole


# ── Company admin ────────────────────────────────────────────────────────


def test_admin_has_full_control_within_company(client, scenario):
    agent_id = scenario["agent"].id
    headers = auth_headers(scenario["admin"])

    assert client.get(f"/api/agents/{agent_id}", headers=headers).status_code == 200
    assert client.patch(f"/api/agents/{agent_id}", json={"description": "x"}, headers=headers).status_code == 200
    assert client.get(f"/api/agents/{agent_id}/shares", headers=headers).status_code == 200
    assert client.get(f"/api/agents/{agent_id}/database", headers=headers).status_code == 404  # authorized, none configured


def test_admin_cannot_cross_company_boundary(client, scenario):
    # scenario["agent"] belongs to Company A; company_b_user is an admin of Company B.
    resp = client.get(f"/api/agents/{scenario['agent'].id}", headers=auth_headers(scenario["company_b_user"]))
    assert resp.status_code == 404


# ── Cross-company ────────────────────────────────────────────────────────


def test_cross_company_member_gets_404_even_knowing_the_id(client, scenario):
    resp = client.get(f"/api/agents/{scenario['agent'].id}", headers=auth_headers(scenario["company_b_user"]))
    assert resp.status_code == 404


# ── Sharing behavior ─────────────────────────────────────────────────────


def test_sharing_the_same_user_twice_upserts_not_duplicates(client, scenario, db):
    from app.repositories import agent_share_repository

    agent_id = scenario["agent"].id
    owner, target = scenario["owner"], scenario["shared_user"]

    first = _share(client, agent_id, owner, target.id)
    assert first.status_code == 200
    second = _share(client, agent_id, owner, target.id)
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]  # same row, not duplicated

    shares = agent_share_repository.list_by_agent(db, agent_id)
    assert len([s for s in shares if s.user_id == target.id]) == 1
    assert [s for s in shares if s.user_id == target.id][0].role == "viewer"


def test_cannot_share_with_user_from_another_company(client, scenario):
    agent_id = scenario["agent"].id
    resp = _share(client, agent_id, scenario["owner"], scenario["company_b_user"].id)
    assert resp.status_code == 400


def test_cannot_share_with_inactive_user(client, scenario):
    agent_id = scenario["agent"].id
    resp = _share(client, agent_id, scenario["owner"], scenario["inactive"].id)
    assert resp.status_code == 400


def test_revoking_share_removes_access(client, scenario):
    agent_id = scenario["agent"].id
    owner, target = scenario["owner"], scenario["shared_user"]

    share = _share(client, agent_id, owner, target.id).json()
    assert client.get(f"/api/agents/{agent_id}", headers=auth_headers(target)).status_code == 200

    del_resp = client.delete(f"/api/agents/{agent_id}/shares/{share['id']}", headers=auth_headers(owner))
    assert del_resp.status_code == 200
    assert client.get(f"/api/agents/{agent_id}", headers=auth_headers(target)).status_code == 404


def test_only_owner_or_admin_can_manage_shares(client, scenario):
    agent_id = scenario["agent"].id
    owner, shared_user, shared_user_2 = scenario["owner"], scenario["shared_user"], scenario["shared_user_2"]
    _share(client, agent_id, owner, shared_user.id)
    _share(client, agent_id, owner, shared_user_2.id)

    assert _share(client, agent_id, shared_user, scenario["outsider"].id).status_code == 403
    assert _share(client, agent_id, shared_user_2, scenario["outsider"].id).status_code == 403


# ── Inactive user ────────────────────────────────────────────────────────


def test_inactive_user_cannot_authenticate_at_all(client, scenario):
    resp = client.get("/api/agents", headers=auth_headers(scenario["inactive"]))
    assert resp.status_code == 401


# ── Agent listing ────────────────────────────────────────────────────────


def test_listing_shows_only_owned_and_shared_agents(client, scenario):
    agent_id = scenario["agent"].id
    owner, shared_user, outsider = scenario["owner"], scenario["shared_user"], scenario["outsider"]

    # Not shared yet — outsider (a plain company member) sees nothing.
    resp = client.get("/api/agents", headers=auth_headers(outsider))
    assert resp.status_code == 200
    assert agent_id not in [a["id"] for a in resp.json()]

    owner_resp = client.get("/api/agents", headers=auth_headers(owner))
    owner_agent = next(a for a in owner_resp.json() if a["id"] == agent_id)
    assert owner_agent["my_role"] == "owner"
    assert owner_agent["shared_by"] is None

    _share(client, agent_id, owner, shared_user.id)
    shared_resp = client.get("/api/agents", headers=auth_headers(shared_user))
    shared_agent = next(a for a in shared_resp.json() if a["id"] == agent_id)
    assert shared_agent["my_role"] == "viewer"
    assert shared_agent["shared_by"]["id"] == owner.id  # granted by the owner, not attributed elsewhere


def test_shared_by_reflects_actual_granter_not_agent_owner(client, scenario):
    """Admin (not the owner) shares the agent with someone — 'shared_by' must be the admin."""
    agent_id = scenario["agent"].id
    admin, shared_user = scenario["admin"], scenario["shared_user"]

    resp = _share(client, agent_id, admin, shared_user.id)
    assert resp.status_code == 200
    assert resp.json()["shared_by"]["id"] == admin.id

    listing = client.get("/api/agents", headers=auth_headers(shared_user)).json()
    shared_agent = next(a for a in listing if a["id"] == agent_id)
    assert shared_agent["shared_by"]["id"] == admin.id


def test_admin_implicit_access_is_not_reported_as_shared(client, scenario):
    agent_id = scenario["agent"].id
    resp = client.get("/api/agents", headers=auth_headers(scenario["admin"]))
    admin_agent = next(a for a in resp.json() if a["id"] == agent_id)
    assert admin_agent["my_role"] == "admin"
    assert admin_agent["shared_by"] is None
    assert admin_agent["shared_at"] is None


def test_owner_and_admin_see_identical_explicit_shares(client, scenario, db):
    """Regression: GET /shares must reflect the agent's actual shares for whoever is
    authorized to manage sharing — never filtered down to 'shares I personally granted'."""
    from app.repositories import agent_share_repository

    agent_id = scenario["agent"].id
    owner, admin = scenario["owner"], scenario["admin"]
    shared_user, shared_user_2 = scenario["shared_user"], scenario["shared_user_2"]

    # owner grants one share, admin grants the other — deliberately different granters.
    assert _share(client, agent_id, owner, shared_user.id).status_code == 200
    assert _share(client, agent_id, admin, shared_user_2.id).status_code == 200

    owner_shares = client.get(f"/api/agents/{agent_id}/shares", headers=auth_headers(owner)).json()
    admin_shares = client.get(f"/api/agents/{agent_id}/shares", headers=auth_headers(admin)).json()

    owner_seen = {(s["user"]["email"], s["role"], s["shared_by"]["email"]) for s in owner_shares}
    admin_seen = {(s["user"]["email"], s["role"], s["shared_by"]["email"]) for s in admin_shares}
    expected = {
        ("shared@company-a.test", "viewer", "owner@company-a.test"),
        ("shared2@company-a.test", "viewer", "admin@company-a.test"),
    }
    assert owner_seen == expected, f"owner should see the agent's real shares, got {owner_seen}"
    assert admin_seen == expected, f"admin should see the same real shares, got {admin_seen}"

    # And confirm the actual DB row count/content matches (not just the API projection).
    db_shares = agent_share_repository.list_by_agent(db, agent_id)
    assert len(db_shares) == 2


def test_admin_implicit_access_creates_no_agent_share_row(client, scenario, db):
    from app.repositories import agent_share_repository

    agent_id = scenario["agent"].id
    admin = scenario["admin"]

    # Admin merely viewing/using the agent must never create a fake AgentShare("admin").
    client.get(f"/api/agents/{agent_id}", headers=auth_headers(admin))
    client.get(f"/api/agents/{agent_id}/shares", headers=auth_headers(admin))

    rows = agent_share_repository.list_by_agent(db, agent_id)
    assert admin.id not in [s.user_id for s in rows]
    assert all(s.role == "viewer" for s in rows)


def test_shared_users_all_reference_the_same_agent_id(client, scenario):
    """Sharing must never clone the agent — every authorized party sees the identical id."""
    agent_id = scenario["agent"].id
    owner, admin = scenario["owner"], scenario["admin"]
    shared_user, shared_user_2 = scenario["shared_user"], scenario["shared_user_2"]
    _share(client, agent_id, owner, shared_user.id)
    _share(client, agent_id, owner, shared_user_2.id)

    for user in (owner, admin, shared_user, shared_user_2):
        listing = client.get("/api/agents", headers=auth_headers(user)).json()
        ids = [a["id"] for a in listing]
        assert ids.count(agent_id) <= 1  # never duplicated
        assert agent_id in ids


# ── Draft agents cannot be shared ───────────────────────────────────────────


def test_draft_agent_cannot_be_shared(client, scenario):
    agent_id = scenario["draft_agent"].id
    owner, target = scenario["owner"], scenario["shared_user"]
    resp = _share(client, agent_id, owner, target.id)
    assert resp.status_code == 400


def test_draft_agent_share_attempt_by_admin_also_rejected(client, scenario):
    agent_id = scenario["draft_agent"].id
    admin, target = scenario["admin"], scenario["shared_user"]
    resp = _share(client, agent_id, admin, target.id)
    assert resp.status_code == 400


def test_ready_agent_can_be_shared(client, scenario):
    """Sanity check that the draft rejection is status-specific, not a general regression."""
    agent_id = scenario["agent"].id  # status="active" in the scenario fixture
    owner, target = scenario["owner"], scenario["shared_user"]
    resp = _share(client, agent_id, owner, target.id)
    assert resp.status_code == 200


def test_draft_agent_does_not_appear_in_recipients_listing(client, scenario, db):
    """A stray AgentShare row on a draft agent (e.g. leftover dev data) must not grant
    access or visibility — access is gated on the agent's current status, not just the
    presence of a share row."""
    from app.models.agent_share import AgentShare

    draft_agent_id = scenario["draft_agent"].id
    owner, target = scenario["owner"], scenario["shared_user"]

    # Bypass the API to simulate stale/legacy data: a share row that exists despite the
    # agent being draft (this is exactly what the API itself now refuses to create).
    db.add(AgentShare(agent_id=draft_agent_id, user_id=target.id, role="viewer", shared_by_id=owner.id))
    db.commit()

    listing = client.get("/api/agents", headers=auth_headers(target)).json()
    assert draft_agent_id not in [a["id"] for a in listing]

    direct = client.get(f"/api/agents/{draft_agent_id}", headers=auth_headers(target))
    assert direct.status_code == 404


def test_owner_and_admin_retain_access_to_draft_agent(client, scenario):
    """Owner/admin must still be able to open and continue setting up a draft agent —
    the sharing boundary only restricts recipients, never the people finishing setup."""
    agent_id = scenario["draft_agent"].id
    assert client.get(f"/api/agents/{agent_id}", headers=auth_headers(scenario["owner"])).status_code == 200
    assert client.get(f"/api/agents/{agent_id}", headers=auth_headers(scenario["admin"])).status_code == 200


def test_agent_creation_flow_unchanged_and_gates_sharing_on_ready_state(client, scenario, db):
    """Minimal integration proof that sharing depends on the agent-creation flow's existing
    status field, without touching or reimplementing that flow: create an agent through the
    real POST /agents endpoint (exactly what the untouched wizard already does), confirm it
    starts in the untouched default "draft" status, confirm sharing it is rejected, then
    confirm sharing works once status reaches "active" — without altering how that status
    transition itself happens."""
    from app.models.agent import Agent

    owner, target = scenario["owner"], scenario["shared_user"]
    create_resp = client.post(
        "/api/agents", json={"name": "Freshly Created Agent"}, headers=auth_headers(owner)
    )
    assert create_resp.status_code == 200
    new_agent = create_resp.json()
    assert new_agent["status"] == "draft"  # unchanged creation-flow default

    assert _share(client, new_agent["id"], owner, target.id).status_code == 400

    agent_row = db.get(Agent, new_agent["id"])
    agent_row.status = "active"
    db.commit()

    assert _share(client, new_agent["id"], owner, target.id).status_code == 200


# ── No legacy "editor" data can grant elevated access ──────────────────────


def test_legacy_editor_share_row_only_grants_viewer_access(client, scenario, db):
    """A share row with the retired role="editor" value (simulating data from before this
    change) must resolve to ordinary use/read access only — never elevated privileges."""
    from app.models.agent_share import AgentShare

    agent_id = scenario["agent"].id
    owner, target = scenario["owner"], scenario["shared_user"]

    db.add(AgentShare(agent_id=agent_id, user_id=target.id, role="editor", shared_by_id=owner.id))
    db.commit()

    headers = auth_headers(target)
    get_resp = client.get(f"/api/agents/{agent_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["my_role"] == "viewer"  # normalized, never "editor"

    assert client.patch(f"/api/agents/{agent_id}", json={"description": "x"}, headers=headers).status_code == 403
    assert client.get(f"/api/agents/{agent_id}/database", headers=headers).status_code == 403
    assert client.get(f"/api/agents/{agent_id}/shares", headers=headers).status_code == 403


# ── Shared user chat access (Shared With Me -> Open Agent -> existing Chat) ─────────────


def test_shared_user_can_reach_and_use_chat(client, scenario):
    """A shared user must be able to open a conversation and read/send messages on the
    Ready agent that was shared with them, via the same chat endpoints the owner uses —
    no separate/duplicate chat surface."""
    agent_id = scenario["agent"].id
    owner, shared_user = scenario["owner"], scenario["shared_user"]
    assert _share(client, agent_id, owner, shared_user.id).status_code == 200

    headers = auth_headers(shared_user)

    # Can list (empty) and create a conversation.
    assert client.get(f"/api/agents/{agent_id}/conversations", headers=headers).status_code == 200
    create_resp = client.post(f"/api/agents/{agent_id}/conversations", headers=headers)
    assert create_resp.status_code == 200
    conversation_id = create_resp.json()["id"]

    # Can read messages on their own conversation via the conversation-scoped routes.
    assert client.get(f"/api/conversations/{conversation_id}/messages", headers=headers).status_code == 200


def test_no_access_user_cannot_reach_conversations_or_messages(client, scenario):
    agent_id = scenario["agent"].id
    owner, outsider = scenario["owner"], scenario["outsider"]

    # Outsider has no share at all — blocked from the agent's conversation list entirely.
    assert client.get(f"/api/agents/{agent_id}/conversations", headers=auth_headers(outsider)).status_code == 404

    # A conversation created by the owner must not be reachable by the outsider either.
    conv = client.post(f"/api/agents/{agent_id}/conversations", headers=auth_headers(owner)).json()
    assert client.get(f"/api/conversations/{conv['id']}/messages", headers=auth_headers(outsider)).status_code == 404
    assert client.delete(f"/api/conversations/{conv['id']}", headers=auth_headers(outsider)).status_code == 404


def test_shared_user_does_not_see_chat_error_message_details(client, scenario, db):
    """A chat message's error_message can echo raw DB-connection exception text (built from
    the agent's real, decrypted connection string) if the reasoning engine fails to
    initialize or query — must be redacted for a shared (viewer) user, same as knowledge
    asset error messages, and left intact for the owner who needs to diagnose it."""
    from app.repositories import conversation_repository, message_repository

    agent_id = scenario["agent"].id
    owner, shared_user = scenario["owner"], scenario["shared_user"]
    assert _share(client, agent_id, owner, shared_user.id).status_code == 200

    conversation = conversation_repository.create(db, agent_id=agent_id, user_id=owner.id)
    message_repository.create(
        db,
        conversation_id=conversation.id,
        role="assistant",
        content="I ran into a problem answering that question.",
        error_message="could not connect to server: host=db.internal.company user=svc password=hunter2 failed",
    )
    db.commit()

    shared_resp = client.get(f"/api/conversations/{conversation.id}/messages", headers=auth_headers(shared_user))
    assert shared_resp.status_code == 200
    assert shared_resp.json()[0]["error_message"] is None

    owner_resp = client.get(f"/api/conversations/{conversation.id}/messages", headers=auth_headers(owner))
    assert owner_resp.status_code == 200
    assert "password=hunter2" in owner_resp.json()[0]["error_message"]
