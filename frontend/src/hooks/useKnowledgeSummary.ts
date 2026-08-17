import { useQuery } from "@tanstack/react-query";
import { getKnowledgeSummary } from "../api/knowledgeSummary";

export function useKnowledgeSummary(agentId: string) {
  return useQuery({
    queryKey: ["knowledge-summary", agentId],
    queryFn: () => getKnowledgeSummary(agentId),
    enabled: !!agentId,
  });
}
