import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  deleteAsset,
  generateAsset,
  listKnowledgeAssets,
  uploadAsset,
  type AssetType,
} from "../api/knowledgeAssets";

const key = (agentId: string) => ["knowledge-assets", agentId] as const;

export function useKnowledgeAssets(agentId: string) {
  return useQuery({ queryKey: key(agentId), queryFn: () => listKnowledgeAssets(agentId) });
}

export function useGenerateAsset(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assetType: AssetType) => generateAsset(agentId, assetType),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key(agentId) }),
  });
}

export function useUploadAsset(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ assetType, file }: { assetType: AssetType; file: File }) =>
      uploadAsset(agentId, assetType, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key(agentId) }),
  });
}

export function useDeleteAsset(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assetType: AssetType) => deleteAsset(agentId, assetType),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key(agentId) }),
  });
}
