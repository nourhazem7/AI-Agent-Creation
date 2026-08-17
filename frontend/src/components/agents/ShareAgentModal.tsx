import { useState } from "react";
import { Badge, Button, Modal, Select } from "../ui";
import {
  useAgentShares,
  useCompanyMembers,
  useRevokeShare,
  useShareAgent,
  useUpdateShareRole,
} from "../../hooks/useAgentShares";
import { SHARE_ROLE_OPTIONS } from "../../lib/shareRole";
import { apiErrorMessage } from "../../api/client";
import type { Agent, ShareRole } from "../../types";

interface ShareAgentModalProps {
  agent: Agent;
  isOpen: boolean;
  onClose: () => void;
}

function initials(name: string | null, email: string): string {
  const source = name?.trim() || email;
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return source.slice(0, 2).toUpperCase();
}

function PersonAvatar({ name, email }: { name: string | null; email: string }) {
  return (
    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-border bg-canvas text-xs font-medium text-ink-muted">
      {initials(name, email)}
    </span>
  );
}

const ROLE_SELECT_OPTIONS = SHARE_ROLE_OPTIONS.map((opt) => ({ value: opt.value, label: opt.meta.label }));

export function ShareAgentModal({ agent, isOpen, onClose }: ShareAgentModalProps) {
  const [mode, setMode] = useState<"list" | "add">("list");
  const [selectedMemberId, setSelectedMemberId] = useState("");
  const [selectedRole, setSelectedRole] = useState<ShareRole>("viewer");
  const [error, setError] = useState<string | null>(null);

  const sharesQuery = useAgentShares(agent.id, isOpen);
  const membersQuery = useCompanyMembers(isOpen && mode === "add");
  const shareMutation = useShareAgent(agent.id);
  const updateRoleMutation = useUpdateShareRole(agent.id);
  const revokeMutation = useRevokeShare(agent.id);

  const shares = sharesQuery.data ?? [];
  const sharedUserIds = new Set(shares.map((s) => s.user.id));
  const availableMembers = (membersQuery.data ?? []).filter(
    (m) => m.id !== agent.owner_id && !sharedUserIds.has(m.id),
  );

  function resetAndClose() {
    setMode("list");
    setSelectedMemberId("");
    setSelectedRole("viewer");
    setError(null);
    onClose();
  }

  async function handleShare() {
    if (!selectedMemberId) return;
    setError(null);
    try {
      await shareMutation.mutateAsync({ userId: selectedMemberId, role: selectedRole });
      setMode("list");
      setSelectedMemberId("");
      setSelectedRole("viewer");
    } catch (err) {
      setError(apiErrorMessage(err, "Could not share the agent."));
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={resetAndClose}
      title={mode === "list" ? `Share ${agent.name}` : "Share with teammate"}
    >
      {mode === "list" ? (
        <div className="flex flex-col gap-4">
          <div>
            <h3 className="mb-3 text-xs font-medium uppercase tracking-wide text-ink-muted">
              People with access
            </h3>
            <div className="flex flex-col gap-4">
              <div className="flex items-center gap-3">
                <PersonAvatar name={agent.owner.full_name} email={agent.owner.email} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-ink">
                    {agent.owner.full_name || agent.owner.email}
                  </p>
                  <p className="truncate text-xs text-ink-muted">{agent.owner.email}</p>
                </div>
                <Badge tone="accent">Owner</Badge>
              </div>

              {sharesQuery.isLoading && <p className="text-sm text-ink-muted">Loading…</p>}

              {shares.map((share) => (
                <div key={share.id} className="flex items-center gap-3">
                  <PersonAvatar name={share.user.full_name} email={share.user.email} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink">
                      {share.user.full_name || share.user.email}
                    </p>
                    <p className="truncate text-xs text-ink-muted">{share.user.email}</p>
                  </div>
                  <div className="w-32">
                    <Select
                      aria-label={`Access level for ${share.user.email}`}
                      options={ROLE_SELECT_OPTIONS}
                      value={share.role}
                      disabled={updateRoleMutation.isPending}
                      onChange={(e) =>
                        updateRoleMutation.mutate({ shareId: share.id, role: e.target.value as ShareRole })
                      }
                    />
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => revokeMutation.mutate(share.id)}
                    disabled={revokeMutation.isPending}
                  >
                    Remove
                  </Button>
                </div>
              ))}

              {!sharesQuery.isLoading && shares.length === 0 && (
                <p className="text-sm text-ink-muted">Only you have access so far.</p>
              )}
            </div>
          </div>

          <Button variant="secondary" onClick={() => setMode("add")} className="self-start">
            + Share with teammate
          </Button>

          <p className="border-t border-border pt-3 text-xs text-ink-muted">
            You're sharing the Agent, not the database. Database credentials and connection
            details remain protected — people you share this Agent with can use it according to
            their access level.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-5">
          <Select
            label="Search people"
            placeholder={membersQuery.isLoading ? "Loading teammates…" : "Select a teammate"}
            options={availableMembers.map((m) => ({
              value: m.id,
              label: m.full_name ? `${m.full_name} · ${m.email}` : m.email,
            }))}
            value={selectedMemberId}
            onChange={(e) => setSelectedMemberId(e.target.value)}
          />
          {!membersQuery.isLoading && availableMembers.length === 0 && (
            <p className="-mt-3 text-xs text-ink-muted">Everyone in your company already has access.</p>
          )}

          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium text-ink">Access</span>
            {SHARE_ROLE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setSelectedRole(opt.value)}
                className={`flex items-start gap-3 rounded-md border px-3 py-2.5 text-left transition-colors
                  ${selectedRole === opt.value ? "border-ink bg-canvas" : "border-border bg-surface hover:bg-canvas"}`}
              >
                <span
                  className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border
                    ${selectedRole === opt.value ? "border-ink" : "border-border"}`}
                  aria-hidden="true"
                >
                  {selectedRole === opt.value && <span className="h-2 w-2 rounded-full bg-ink" />}
                </span>
                <span>
                  <span className="block text-sm font-medium text-ink">{opt.meta.label}</span>
                  <span className="block text-xs text-ink-muted">{opt.meta.description}</span>
                </span>
              </button>
            ))}
          </div>

          {error && <p className="text-sm text-danger">{error}</p>}

          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setMode("list")}>
              Cancel
            </Button>
            <Button onClick={handleShare} isLoading={shareMutation.isPending} disabled={!selectedMemberId}>
              Share Agent
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
