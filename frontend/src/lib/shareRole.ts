import type { ShareRole } from "../types";

interface ShareRoleMeta {
  label: string;
  description: string;
}

// The backend term "viewer" never reaches JSX directly — this is the one place that
// translates it into the product's friendlier sharing language. There is only one shared
// role: a shared user can use/chat with an Agent, never modify it.
const SHARE_ROLE_META: Record<ShareRole, ShareRoleMeta> = {
  viewer: { label: "Can Chat", description: "Ask questions and use the Agent." },
};

export function shareRoleMeta(role: ShareRole): ShareRoleMeta {
  return SHARE_ROLE_META[role];
}
