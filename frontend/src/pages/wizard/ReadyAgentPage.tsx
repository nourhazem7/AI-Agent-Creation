import { useNavigate, useParams } from "react-router-dom";
import { Button, Card } from "../../components/ui";
import { useAgent } from "../../hooks/useAgents";

function ChecklistRow({ label, done }: { label: string; done: boolean }) {
  return (
    <li className="flex items-center gap-2 text-sm">
      <span className={done ? "text-success" : "text-ink-muted"}>{done ? "✓" : "○"}</span>
      <span className={done ? "text-ink" : "text-ink-muted"}>{label}</span>
    </li>
  );
}

export default function ReadyAgentPage() {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();
  const { data: agent } = useAgent(agentId);

  if (!agentId) return null;

  const validationCompleted = agent?.status === "validated" || agent?.status === "active";

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="text-xl font-semibold text-ink">Your agent is ready</h1>
      <p className="mt-1 text-sm text-ink-muted">
        {agent?.name ?? "This agent"} is set up and ready to answer questions about your database.
      </p>

      <div className="mt-6 rounded-lg border border-success/20 bg-success/10 px-4 py-3 text-sm text-success">
        Setup complete — you can start chatting now.
      </div>

      <Card className="mt-6 p-5">
        <ul className="flex flex-col gap-2">
          <ChecklistRow label="Database connected" done={!!agent?.database_connected} />
          <ChecklistRow
            label="Knowledge configured"
            done={!!agent && agent.knowledge_ready_count === agent.knowledge_total_count}
          />
          <ChecklistRow label="Validation completed" done={validationCompleted} />
        </ul>
      </Card>

      <div className="mt-6 flex justify-end">
        <Button onClick={() => navigate(`/agents/${agentId}/chat`)}>Start chatting</Button>
      </div>
    </div>
  );
}