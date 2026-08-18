import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listShares, revokeShare, shareAgent } from "../api/agentShares";
import { listCompanyMembers } from "../api/companies";

const AGENTS_KEY = ["agents"] as const;
const sharesKey = (agentId: string) => ["agents", agentId, "shares"] as const;

export function useAgentShares(agentId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: sharesKey(agentId ?? ""),
    queryFn: () => listShares(agentId as string),
    enabled: !!agentId && enabled,
  });
}

export function useCompanyMembers(enabled = true) {
  return useQuery({ queryKey: ["companies", "members"], queryFn: listCompanyMembers, enabled });
}

export function useShareAgent(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => shareAgent(agentId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sharesKey(agentId) });
      queryClient.invalidateQueries({ queryKey: AGENTS_KEY });
    },
  });
}

export function useRevokeShare(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (shareId: string) => revokeShare(agentId, shareId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sharesKey(agentId) });
      queryClient.invalidateQueries({ queryKey: AGENTS_KEY });
    },
  });
}
