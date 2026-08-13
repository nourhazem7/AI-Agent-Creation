import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { DialectSelector } from "../../components/database/DialectSelector";
import { ConnectionForm } from "../../components/database/ConnectionForm";
import type { DialectMeta } from "../../lib/dialects";

export default function ConnectDatabasePage() {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();
  const [selectedDialect, setSelectedDialect] = useState<DialectMeta | null>(null);

  if (!agentId) return null;

  return (
    <div className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="text-xl font-semibold text-ink">Connect your database</h1>
      <p className="mt-1 text-sm text-ink-muted">
        Your credentials are encrypted and only used by this agent to answer questions.
      </p>

      <div className="mt-8">
        {!selectedDialect ? (
          <DialectSelector onSelect={setSelectedDialect} />
        ) : (
          <ConnectionForm
            agentId={agentId}
            dialect={selectedDialect}
            onBack={() => setSelectedDialect(null)}
            onConnected={() => navigate(`/agents/${agentId}/knowledge`)}
          />
        )}
      </div>
    </div>
  );
}
