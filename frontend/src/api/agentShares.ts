import { apiClient } from "./client";
import type { AgentShare } from "../types";

export async function listShares(agentId: string): Promise<AgentShare[]> {
  const { data } = await apiClient.get<AgentShare[]>(`/agents/${agentId}/shares`);
  return data;
}

// A share always grants use/read access ("viewer") — there is no role to choose.
export async function shareAgent(agentId: string, userId: string): Promise<AgentShare> {
  const { data } = await apiClient.post<AgentShare>(`/agents/${agentId}/shares`, {
    user_id: userId,
    role: "viewer",
  });
  return data;
}

export async function revokeShare(agentId: string, shareId: string): Promise<void> {
  await apiClient.delete(`/agents/${agentId}/shares/${shareId}`);
}
