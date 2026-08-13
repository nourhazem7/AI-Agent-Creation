import { apiClient } from "./client";

export type AssetType = "schema" | "documentation" | "validation_suite";
export type AssetStatus = "not_configured" | "generating" | "ready" | "error";
export type AssetSource = "generated" | "uploaded" | null;

export interface KnowledgeAsset {
  id?: string;
  agent_id?: string;
  asset_type: AssetType;
  source: AssetSource;
  status: AssetStatus;
  content?: string | null;
  original_filename?: string | null;
  error_message?: string | null;
  created_at?: string;
  updated_at?: string;
}

export async function listKnowledgeAssets(agentId: string): Promise<KnowledgeAsset[]> {
  const { data } = await apiClient.get<KnowledgeAsset[]>(`/agents/${agentId}/knowledge-assets`);
  return data;
}

export async function generateAsset(agentId: string, assetType: AssetType): Promise<KnowledgeAsset> {
  const { data } = await apiClient.post<KnowledgeAsset>(
    `/agents/${agentId}/knowledge-assets/${assetType}/generate`,
  );
  return data;
}

export async function uploadAsset(agentId: string, assetType: AssetType, file: File): Promise<KnowledgeAsset> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post<KnowledgeAsset>(
    `/agents/${agentId}/knowledge-assets/${assetType}/upload`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return data;
}

export async function deleteAsset(agentId: string, assetType: AssetType): Promise<void> {
  await apiClient.delete(`/agents/${agentId}/knowledge-assets/${assetType}`);
}
