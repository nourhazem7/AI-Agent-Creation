import { Link, useParams } from "react-router-dom";
import { Button } from "../../components/ui";

// Real multi-stage progress (schema confirm -> docs -> validation suite -> engine
// warm-up) is still a stub — the underlying operations it would show progress for
// (schema/documentation/validation generation) are already real, built in Milestone 5.
// This page just needs to visualize that sequence; not yet built.
export default function PreparationPage() {
  const { agentId } = useParams<{ agentId: string }>();
  if (!agentId) return null;

  return (
    <div className="mx-auto max-w-2xl px-6 py-16 text-center">
      <h1 className="text-lg font-semibold text-ink">Knowledge Assets configured ✓</h1>
      <p className="mt-2 text-sm text-ink-muted">
        A visual step-by-step preparation view is coming soon. Your knowledge assets are
        already generated and verified — continue to see what this agent has learned.
      </p>
      <Link to={`/agents/${agentId}/summary`} className="mt-6 inline-block">
        <Button>View Knowledge Summary</Button>
      </Link>
    </div>
  );
}
