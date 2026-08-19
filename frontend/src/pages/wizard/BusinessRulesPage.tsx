import { useState } from "react";
import { useParams } from "react-router-dom";
import { Button, Card } from "../../components/ui";
import { AddBusinessRuleModal } from "../../components/agents/AddBusinessRuleModal";
import { useAgentMemory, useDeleteAgentMemory } from "../../hooks/useAgentMemory";
import { apiErrorMessage } from "../../api/client";

function formatAddedDate(isoString: string): string {
  return new Date(isoString).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function BusinessRulesPage() {
  const { agentId } = useParams<{ agentId: string }>();
  const { data: rules, isLoading, isError, error } = useAgentMemory(agentId ?? "");
  const deleteRule = useDeleteAgentMemory(agentId ?? "");
  const [isAddOpen, setIsAddOpen] = useState(false);

  if (!agentId) return null;

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <div className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-ink">Business Rules</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Rules and definitions this agent should remember when answering questions.
          </p>
        </div>
        {!!rules?.length && <Button onClick={() => setIsAddOpen(true)}>+ Add business rule</Button>}
      </div>

      {isLoading && (
        <div className="flex justify-center py-16">
          <span className="h-6 w-6 animate-spin rounded-full border-2 border-ink border-t-transparent" />
        </div>
      )}

      {isError && (
        <p className="rounded-md border border-danger/20 bg-danger/5 px-4 py-3 text-sm text-danger">
          Couldn't load business rules: {apiErrorMessage(error)}
        </p>
      )}

      {!isLoading && !isError && rules?.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-surface px-6 py-16 text-center">
          <h2 className="text-base font-semibold text-ink">No business rules yet</h2>
          <p className="mt-2 max-w-sm text-sm text-ink-muted">
            Business rules are optional. Add one whenever there's a definition or rule this
            agent should apply when answering questions.
          </p>
          <Button className="mt-6" onClick={() => setIsAddOpen(true)}>
            + Add business rule
          </Button>
        </div>
      )}

      {!isLoading && !isError && !!rules?.length && (
        <div className="flex flex-col gap-3">
          {rules.map((rule) => (
            <Card key={rule.id} className="flex items-start justify-between gap-4 p-4">
              <div className="min-w-0">
                <p className="whitespace-pre-wrap text-sm text-ink">{rule.content}</p>
                <p className="mt-2 text-xs text-ink-muted">Added {formatAddedDate(rule.created_at)}</p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => deleteRule.mutate(rule.id)}
                disabled={deleteRule.isPending}
              >
                Delete
              </Button>
            </Card>
          ))}
        </div>
      )}

      <AddBusinessRuleModal agentId={agentId} isOpen={isAddOpen} onClose={() => setIsAddOpen(false)} />
    </div>
  );
}
