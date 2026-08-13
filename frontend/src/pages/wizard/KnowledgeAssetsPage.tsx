import { useNavigate, useParams } from "react-router-dom";
import { AssetCard } from "../../components/knowledge/AssetCard";
import { Button } from "../../components/ui";
import { useKnowledgeAssets } from "../../hooks/useKnowledgeAssets";
import { KNOWLEDGE_ASSET_META, KNOWLEDGE_ASSET_ORDER } from "../../lib/knowledgeAssetMeta";
import { apiErrorMessage } from "../../api/client";

export default function KnowledgeAssetsPage() {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();
  const { data: assets, isLoading, isError, error } = useKnowledgeAssets(agentId as string);

  if (!agentId) return null;

  const byType = new Map((assets ?? []).map((a) => [a.asset_type, a]));
  const readyCount = KNOWLEDGE_ASSET_ORDER.filter((t) => byType.get(t)?.status === "ready").length;
  const allReady = readyCount === KNOWLEDGE_ASSET_ORDER.length;

  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
      <h1 className="text-xl font-semibold text-ink">Knowledge Assets</h1>
      <p className="mt-1 text-sm text-ink-muted">
        Choose how the agent should build its understanding of your database — generate each
        automatically or upload your own.
      </p>

      {isLoading && (
        <div className="mt-10 flex justify-center">
          <span className="h-6 w-6 animate-spin rounded-full border-2 border-ink border-t-transparent" />
        </div>
      )}

      {isError && (
        <p className="mt-6 rounded-md border border-danger/20 bg-danger/5 px-4 py-3 text-sm text-danger">
          Couldn't load knowledge assets: {apiErrorMessage(error)}
        </p>
      )}

      {!isLoading && !isError && (
        <>
          <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {KNOWLEDGE_ASSET_ORDER.map((type) => (
              <AssetCard
                key={type}
                agentId={agentId}
                assetType={type}
                asset={byType.get(type) ?? { asset_type: type, source: null, status: "not_configured" }}
              />
            ))}
          </div>

          <div className="mt-8 rounded-lg border border-border bg-surface p-4">
            <p className="text-sm font-medium text-ink">Knowledge Assets</p>
            <ul className="mt-2 flex flex-col gap-1">
              {KNOWLEDGE_ASSET_ORDER.map((type) => {
                const ready = byType.get(type)?.status === "ready";
                return (
                  <li key={type} className="flex items-center gap-2 text-sm">
                    <span className={ready ? "text-success" : "text-ink-muted"}>{ready ? "✓" : "○"}</span>
                    <span className={ready ? "text-ink" : "text-ink-muted"}>{KNOWLEDGE_ASSET_META[type].title}</span>
                  </li>
                );
              })}
            </ul>
          </div>

          <div className="mt-6 flex justify-end">
            <Button
              disabled={!allReady}
              onClick={() => navigate(`/agents/${agentId}/preparing`)}
              title={allReady ? undefined : "Configure all three knowledge assets to continue"}
            >
              Start Testing
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
