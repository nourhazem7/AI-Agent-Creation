import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createAgent, deleteAgent, getAgent, listAgents, type CreateAgentPayload } from "../api/agents";

const AGENTS_KEY = ["agents"] as const;
const agentKey = (agentId: string) => ["agents", agentId] as const;

export function useAgents() {
  return useQuery({ queryKey: AGENTS_KEY, queryFn: listAgents });
}

export function useAgent(agentId: string | undefined) {
  return useQuery({
    queryKey: agentKey(agentId ?? ""),
    queryFn: () => getAgent(agentId as string),
    enabled: !!agentId,
  });
}

export function useCreateAgent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateAgentPayload) => createAgent(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: AGENTS_KEY });
    },
  });
}

export function useDeleteAgent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (agentId: string) => deleteAgent(agentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: AGENTS_KEY });
    },
  });
}
