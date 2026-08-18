"""Central Agent access-role resolution — the single place that knows how owner/admin/
viewer (a shared user's use/read-only access) are derived. Used by both app/deps.py
(FastAPI dependency wiring) and app/services/agent_service.py (listing) so the rule is
never duplicated.

There is no "editor" role: a shared user can use an Agent (read it, chat with it, once
chat ships) but never modify it, its knowledge, its validation, or its database connection
— only the owner and company admins can. If a user wants a customized Agent, they create
their own; they never gain write access to someone else's.
"""

from __future__ import annotations

from app.models.agent import SHAREABLE_STATUSES, Agent
from app.models.agent_share import AgentShare
from app.models.user import User

# owner and admin are equal-rank (both full control); viewer (any explicit share) is the
# single, strictly-lower "shared user" tier below that.
_ACCESS_RANK = {"viewer": 1, "admin": 2, "owner": 2}


def resolve_role(agent: Agent, user: User, share: AgentShare | None) -> str | None:
    """Compute `user`'s access role on `agent`, given their pre-fetched AgentShare (or None).

    Company boundary is checked first and is absolute — an admin or an existing share can
    never grant access across companies.

    An explicit share only grants access once the agent has finished its setup lifecycle
    (agent.status in SHAREABLE_STATUSES) — a Draft/in-progress agent stays owner/admin-only
    even if a share row exists for it (e.g. stale dev data, or an agent an owner reset after
    sharing it). Owner and admin access is never gated by status — they're the ones who need
    to actually finish setup.

    A share always resolves to "viewer" regardless of what's stored in `share.role` — there
    is only one shared-user access level now. This also means a pre-existing row with the
    retired role="editor" value (if one exists in an already-deployed database) can never
    grant anything beyond ordinary use/read access; the stored value is never trusted.
    """
    if agent.company_id != user.company_id:
        return None
    if agent.owner_id == user.id:
        return "owner"
    if user.role == "admin":
        return "admin"
    if share is not None and agent.status in SHAREABLE_STATUSES:
        return "viewer"
    return None


def has_min_role(role: str | None, minimum: str) -> bool:
    if role is None:
        return False
    return _ACCESS_RANK[role] >= _ACCESS_RANK[minimum]
