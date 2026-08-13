import { Link } from "react-router-dom";
import { AppShell } from "../components/layout/AppShell";
import { Button, Badge, Card } from "../components/ui";
import { useAgents } from "../hooks/useAgents";
import { agentResumePath, agentStatusDisplay } from "../lib/agentStatus";
import { apiErrorMessage } from "../api/client";

export default function DashboardPage() {
  const { data: agents, isLoading, isError, error } = useAgents();

  return (
    <AppShell>
      <div className="mx-auto flex max-w-5xl flex-col px-6 py-10">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-ink">Agents</h1>
            <p className="mt-1 text-sm text-ink-muted">
              Business agents connected to your company's data.
            </p>
          </div>
          {!!agents?.length && (
            <Link to="/agents/new">
              <Button>Create Agent</Button>
            </Link>
          )}
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
            Couldn't load your agents: {apiErrorMessage(error)}
          </div>
        )}

        {!isLoading && !isError && agents?.length === 0 && (
          <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-surface px-6 py-20 text-center">
            <h2 className="text-lg font-semibold text-ink">Create your first Business Agent</h2>
            <p className="mt-2 max-w-sm text-sm text-ink-muted">
              Connect your company's data and turn it into a conversational AI assistant.
            </p>
            <Link to="/agents/new" className="mt-6">
              <Button>Create Agent</Button>
            </Link>
          </div>
        )}

        {!isLoading && !isError && !!agents?.length && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {agents.map((agent) => {
              const status = agentStatusDisplay(agent.status);
              return (
                <Link key={agent.id} to={agentResumePath(agent.id, agent.status)}>
                  <Card interactive className="flex h-full flex-col gap-3 p-5">
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="font-medium text-ink">{agent.name}</h3>
                      <Badge tone={status.tone}>{status.label}</Badge>
                    </div>
                    <p className="line-clamp-2 flex-1 text-sm text-ink-muted">
                      {agent.description || "No description yet."}
                    </p>
                  </Card>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </AppShell>
  );
}
