import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createAgentMemory, deleteAgentMemory, listAgentMemory } from "../api/agentMemory";

const key = (agentId: string) => ["agent-memory", agentId] as const;

export function useAgentMemory(agentId: string) {
  return useQuery({ queryKey: key(agentId), queryFn: () => listAgentMemory(agentId) });
}

export function useCreateAgentMemory(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (content: string) => createAgentMemory(agentId, content),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key(agentId) }),
  });
}

export function useDeleteAgentMemory(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (memoryId: string) => deleteAgentMemory(agentId, memoryId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key(agentId) }),
  });
}
