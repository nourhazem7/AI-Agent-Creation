import { Link } from "react-router-dom";
import { AppShell } from "../components/layout/AppShell";
import { AgentListTabs } from "../components/agents/AgentListTabs";
import { Badge, Button, Card } from "../components/ui";
import { useAgents } from "../hooks/useAgents";
import { agentResumePath, agentStatusDisplay } from "../lib/agentStatus";
import { shareRoleMeta } from "../lib/shareRole";
import { apiErrorMessage } from "../api/client";
import type { ShareRole } from "../types";

export default function SharedWithMePage() {
  const { data: allAgents, isLoading, isError, error } = useAgents();

  // Only agents reached through an explicit AgentShare — never an admin's implicit
  // company-wide reach, so this page never misrepresents administrative access as a share.
  const agents = allAgents?.filter((a) => a.my_role === "editor" || a.my_role === "viewer");

  return (
    <AppShell>
      <div className="mx-auto flex max-w-5xl flex-col px-6 py-10">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-ink">Agents</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Business agents connected to your company's data.
          </p>
        </div>

        <div className="mb-8">
          <AgentListTabs />
        </div>

        {isLoading && (
          <div className="flex justify-center py-20">
            <span
              className="h-6 w-6 animate-spin rounded-full border-2 border-ink border-t-transparent"
              aria-label="Loading agents"
            />
          </div>
        )}

        {isError && (
          <div className="rounded-lg border border-danger/20 bg-danger/5 px-4 py-3 text-sm text-danger">
            Couldn't load shared agents: {apiErrorMessage(error)}
          </div>
        )}

        {!isLoading && !isError && agents?.length === 0 && (
          <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-surface px-6 py-20 text-center">
            <h2 className="text-lg font-semibold text-ink">Nothing shared with you yet</h2>
            <p className="mt-2 max-w-sm text-sm text-ink-muted">
              When a teammate shares an Agent with you, it'll show up here.
            </p>
          </div>
        )}

        {!isLoading && !isError && !!agents?.length && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {agents.map((agent) => {
              const status = agentStatusDisplay(agent.status);
              const roleMeta = shareRoleMeta(agent.my_role as ShareRole);
              const sharedByName = agent.shared_by?.full_name || agent.shared_by?.email;
              return (
                <Card key={agent.id} className="flex h-full flex-col gap-3 p-5">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="font-medium text-ink">{agent.name}</h3>
                    <Badge tone={status.tone}>{status.label}</Badge>
                  </div>
                  <p className="line-clamp-2 flex-1 text-sm text-ink-muted">
                    {agent.description || "No description yet."}
                  </p>
                  <div className="flex items-center justify-between gap-2 text-xs text-ink-muted">
                    {sharedByName && <span>Shared by {sharedByName}</span>}
                    <Badge tone="neutral">{roleMeta.label}</Badge>
                  </div>
                  <Link to={agentResumePath(agent.id, agent.status)}>
                    <Button variant="secondary" className="w-full">
                      Open Agent
                    </Button>
                  </Link>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </AppShell>
  );
}
