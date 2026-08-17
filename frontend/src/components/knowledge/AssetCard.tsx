import { useState } from "react";
import { Badge, Button, Card } from "../ui";
import { AssetConfigModal } from "./AssetConfigModal";
import { KNOWLEDGE_ASSET_META } from "../../lib/knowledgeAssetMeta";
import { assetSummaryLine, assetVerificationLabel } from "../../lib/knowledgeAssetPreview";
import type { AssetType, KnowledgeAsset } from "../../api/knowledgeAssets";

interface AssetCardProps {
  agentId: string;
  assetType: AssetType;
  asset: KnowledgeAsset;
}

export function AssetCard({ agentId, assetType, asset }: AssetCardProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const meta = KNOWLEDGE_ASSET_META[assetType];
  const isReady = asset.status === "ready";
  const isError = asset.status === "error";
  const summary = isReady ? assetSummaryLine(assetType, asset.content) : null;
  const verificationLabel = isReady
    ? assetVerificationLabel(assetType, asset.source, asset.status, asset.content)
    : null;

  return (
    <>
      <Card className="flex flex-col gap-3 p-5">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-medium text-ink">{meta.title}</h3>
          {isReady && (
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-success/10 text-success">
              ✓
            </span>
          )}
          {isError && <Badge tone="danger">Error</Badge>}
        </div>

        <p className="flex-1 text-sm text-ink-muted">{meta.description}</p>

        {isReady && summary && (
          <p className="text-xs text-ink-muted">
            {summary} · {asset.source === "generated" ? "Generated" : "Uploaded"}
          </p>
        )}
        {isReady && verificationLabel && (
          <p className="text-xs text-success">✓ {verificationLabel}</p>
        )}
        {isError && asset.error_message && (
          <p className="text-xs text-danger">{asset.error_message}</p>
        )}

        <Button variant={isReady ? "secondary" : "primary"} onClick={() => setIsModalOpen(true)}>
          {isReady ? "View / Replace" : isError ? "Retry" : "Configure"}
        </Button>
      </Card>

      <AssetConfigModal
        agentId={agentId}
        assetType={assetType}
        asset={asset}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
      />
    </>
  );
}
