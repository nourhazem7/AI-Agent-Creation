import { useParams } from "react-router-dom";

// Real multi-stage progress (schema confirm -> docs -> validation suite -> engine
// warm-up), driven by actual backend operations, is built in Milestone 6.
export default function PreparationPage() {
  const { agentId } = useParams<{ agentId: string }>();

  return (
    <div className="mx-auto max-w-2xl px-6 py-16 text-center">
      <h1 className="text-lg font-semibold text-ink">Knowledge Assets configured ✓</h1>
      <p className="mt-2 text-sm text-ink-muted">
        Agent preparation for {agentId} — built next.
      </p>
    </div>
  );
}
