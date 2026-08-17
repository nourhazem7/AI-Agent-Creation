import type { AgentStatus } from "../types";

interface StatusDisplay {
  label: string;
  tone: "neutral" | "success" | "warning" | "danger" | "accent";
}

const STATUS_DISPLAY: Record<AgentStatus, StatusDisplay> = {
  draft: { label: "Draft", tone: "neutral" },
  connecting: { label: "Connecting", tone: "warning" },
  configuring_knowledge: { label: "Configuring knowledge", tone: "warning" },
  preparing: { label: "Preparing", tone: "warning" },
  ready_for_validation: { label: "Ready for validation", tone: "accent" },
  validated: { label: "Validated", tone: "success" },
  active: { label: "Active", tone: "success" },
  error: { label: "Needs attention", tone: "danger" },
};

export function agentStatusDisplay(status: AgentStatus): StatusDisplay {
  return STATUS_DISPLAY[status] ?? { label: status, tone: "neutral" };
}

// Mirrors backend SHAREABLE_STATUSES (app/models/agent.py) — an agent can only be shared
// once it's reached "Ready" (validated) or beyond. This only hides the Share affordance
// early; the backend is the actual enforcement point.
const SHAREABLE_STATUSES: readonly AgentStatus[] = ["validated", "active"];

export function isShareable(status: AgentStatus): boolean {
  return SHAREABLE_STATUSES.includes(status);
}

/** Where clicking an agent card should resume the lifecycle, based on its current status. */
export function agentResumePath(agentId: string, status: AgentStatus): string {
  switch (status) {
    case "draft":
    case "connecting":
      return `/agents/${agentId}/connect`;
    case "configuring_knowledge":
      return `/agents/${agentId}/knowledge`;
    case "preparing":
      return `/agents/${agentId}/preparing`;
    case "ready_for_validation":
      return `/agents/${agentId}/validate`;
    case "validated":
      return `/agents/${agentId}/ready`;
    case "active":
      return `/agents/${agentId}/chat`;
    case "error":
    default:
      return `/agents/${agentId}/connect`;
  }
}
