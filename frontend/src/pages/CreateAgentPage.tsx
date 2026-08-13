import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { AppShell } from "../components/layout/AppShell";
import { Button, Input } from "../components/ui";
import { useCreateAgent } from "../hooks/useAgents";
import { agentResumePath } from "../lib/agentStatus";
import { apiErrorMessage } from "../api/client";

// No model/provider picker here on purpose — which LLM an agent uses is a deployment
// concern configured once on the backend (Settings.llm_model), not a per-agent choice
// the user makes at creation time. Keeps the UI unchanged if the configured
// provider/model/endpoint ever changes.
export default function CreateAgentPage() {
  const navigate = useNavigate();
  const createAgent = useCreateAgent();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const agent = await createAgent.mutateAsync({
        name,
        description: description || undefined,
      });
      navigate(agentResumePath(agent.id, agent.status));
    } catch (err) {
      setError(apiErrorMessage(err, "Could not create the agent."));
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-lg px-6 py-12">
        <h1 className="text-xl font-semibold text-ink">Create a Business Agent</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Give it a name — you'll connect its database and knowledge in the next steps.
        </p>

        <form onSubmit={handleSubmit} className="mt-8 flex flex-col gap-5">
          <Input
            label="Agent name"
            name="name"
            placeholder="e.g. Sales Analytics"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />

          <div className="flex flex-col gap-1.5">
            <label htmlFor="description" className="text-sm font-medium text-ink">
              Description <span className="font-normal text-ink-muted">(optional)</span>
            </label>
            <textarea
              id="description"
              rows={3}
              className="rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink
                placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-ink/20"
              placeholder="What should this agent help with?"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          {error && <p className="text-sm text-danger">{error}</p>}

          <Button type="submit" isLoading={createAgent.isPending} className="mt-2">
            Continue
          </Button>
        </form>
      </div>
    </AppShell>
  );
}
