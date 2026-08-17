"""Central Agent access-role resolution — the single place that knows how owner/admin/
editor/viewer are derived. Used by both app/deps.py (FastAPI dependency wiring) and
app/services/agent_service.py (listing) so the rule is never duplicated.
"""

from __future__ import annotations

from app.models.agent import SHAREABLE_STATUSES, Agent
from app.models.agent_share import AgentShare
from app.models.user import User

# owner and admin are equal-rank (both full control); editor and viewer below that.
_ACCESS_RANK = {"viewer": 1, "editor": 2, "admin": 3, "owner": 3}


def resolve_role(agent: Agent, user: User, share: AgentShare | None) -> str | None:
    """Compute `user`'s access role on `agent`, given their pre-fetched AgentShare (or None).

    Company boundary is checked first and is absolute — an admin or an existing share can
    never grant access across companies.

    An explicit share only grants access once the agent has finished its setup lifecycle
    (agent.status in SHAREABLE_STATUSES) — a Draft/in-progress agent stays owner/admin-only
    even if a share row exists for it (e.g. stale dev data, or an agent an owner reset after
    sharing it). Owner and admin access is never gated by status — they're the ones who need
    to actually finish setup.
    """
    if agent.company_id != user.company_id:
        return None
    if agent.owner_id == user.id:
        return "owner"
    if user.role == "admin":
        return "admin"
    if share is not None and agent.status in SHAREABLE_STATUSES:
        return share.role
    return None


def has_min_role(role: str | None, minimum: str) -> bool:
    if role is None:
        return False
    return _ACCESS_RANK[role] >= _ACCESS_RANK[minimum]
