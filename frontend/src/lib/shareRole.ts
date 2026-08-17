import type { ShareRole } from "../types";

interface ShareRoleMeta {
  label: string;
  description: string;
}

// Backend terms (viewer/editor) never reach JSX directly — this is the one place that
// translates them into the product's friendlier sharing language.
const SHARE_ROLE_META: Record<ShareRole, ShareRoleMeta> = {
  viewer: { label: "Can Chat", description: "Ask questions and use the Agent." },
  editor: { label: "Collaborate", description: "Help improve the Agent's knowledge and validation." },
};

export function shareRoleMeta(role: ShareRole): ShareRoleMeta {
  return SHARE_ROLE_META[role];
}

export const SHARE_ROLE_OPTIONS: { value: ShareRole; meta: ShareRoleMeta }[] = [
  { value: "viewer", meta: SHARE_ROLE_META.viewer },
  { value: "editor", meta: SHARE_ROLE_META.editor },
];
