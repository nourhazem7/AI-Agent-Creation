import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listShares, revokeShare, shareAgent, updateShareRole } from "../api/agentShares";
import { listCompanyMembers } from "../api/companies";
import type { ShareRole } from "../types";

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
    mutationFn: ({ userId, role }: { userId: string; role: ShareRole }) => shareAgent(agentId, userId, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sharesKey(agentId) });
      queryClient.invalidateQueries({ queryKey: AGENTS_KEY });
    },
  });
}

export function useUpdateShareRole(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ shareId, role }: { shareId: string; role: ShareRole }) =>
      updateShareRole(agentId, shareId, role),
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
