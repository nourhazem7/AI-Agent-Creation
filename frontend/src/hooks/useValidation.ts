import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createValidationTest,
  deleteValidationTest,
  getValidationSummary,
  listValidationTests,
  runAllValidationTests,
  runFailedValidationTests,
  runValidationTest,
  type CreateTestPayload,
} from "../api/validation";

// Every query/mutation key is scoped by agentId — the same isolation pattern used by
// useAgents/useKnowledgeAssets — so switching agents never shows stale data from another one.
const testsKey = (agentId: string) => ["validation-tests", agentId] as const;
const summaryKey = (agentId: string) => ["validation-summary", agentId] as const;

export function useValidationTests(agentId: string) {
  return useQuery({ queryKey: testsKey(agentId), queryFn: () => listValidationTests(agentId), enabled: !!agentId });
}

export function useValidationSummary(agentId: string) {
  return useQuery({
    queryKey: summaryKey(agentId),
    queryFn: () => getValidationSummary(agentId),
    enabled: !!agentId,
  });
}

function invalidateAgent(queryClient: ReturnType<typeof useQueryClient>, agentId: string) {
  queryClient.invalidateQueries({ queryKey: testsKey(agentId) });
  queryClient.invalidateQueries({ queryKey: summaryKey(agentId) });
}

export function useCreateValidationTest(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateTestPayload) => createValidationTest(agentId, payload),
    onSuccess: () => invalidateAgent(queryClient, agentId),
  });
}

export function useDeleteValidationTest(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (testId: string) => deleteValidationTest(agentId, testId),
    onSuccess: () => invalidateAgent(queryClient, agentId),
  });
}

export function useRunValidationTest(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (testId: string) => runValidationTest(agentId, testId),
    onSuccess: () => invalidateAgent(queryClient, agentId),
  });
}

export function useRunAllValidationTests(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => runAllValidationTests(agentId),
    onSuccess: () => invalidateAgent(queryClient, agentId),
  });
}

export function useRunFailedValidationTests(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => runFailedValidationTests(agentId),
    onSuccess: () => invalidateAgent(queryClient, agentId),
  });
}
