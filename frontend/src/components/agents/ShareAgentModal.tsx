import { useState } from "react";
import { Badge, Button, Modal, Select } from "../ui";
import { useAgentShares, useCompanyMembers, useRevokeShare, useShareAgent } from "../../hooks/useAgentShares";
import { shareRoleMeta } from "../../lib/shareRole";
import { apiErrorMessage } from "../../api/client";
import type { Agent } from "../../types";

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

const CAN_CHAT_LABEL = shareRoleMeta("viewer").label;

export function ShareAgentModal({ agent, isOpen, onClose }: ShareAgentModalProps) {
  const [mode, setMode] = useState<"list" | "add">("list");
  const [selectedMemberId, setSelectedMemberId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const sharesQuery = useAgentShares(agent.id, isOpen);
  const membersQuery = useCompanyMembers(isOpen && mode === "add");
  const shareMutation = useShareAgent(agent.id);
  const revokeMutation = useRevokeShare(agent.id);

  const shares = sharesQuery.data ?? [];
  const sharedUserIds = new Set(shares.map((s) => s.user.id));
  const availableMembers = (membersQuery.data ?? []).filter(
    (m) => m.id !== agent.owner_id && !sharedUserIds.has(m.id),
  );

  function resetAndClose() {
    setMode("list");
    setSelectedMemberId("");
    setError(null);
    onClose();
  }

  async function handleShare() {
    if (!selectedMemberId) return;
    setError(null);
    try {
      await shareMutation.mutateAsync(selectedMemberId);
      setMode("list");
      setSelectedMemberId("");
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
                  <Badge tone="neutral">{CAN_CHAT_LABEL}</Badge>
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
            details remain protected — people you share this Agent with can use and chat with
            it, but can't modify it. To customize an Agent, create your own.
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

          <p className="text-xs text-ink-muted">
            They'll be able to {CAN_CHAT_LABEL.toLowerCase()} with this Agent. They won't be able to
            change it, its knowledge, or its database connection.
          </p>

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
