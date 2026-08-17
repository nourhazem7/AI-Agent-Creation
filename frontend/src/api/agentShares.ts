import { apiClient } from "./client";
import type { AgentShare, ShareRole } from "../types";

export async function listShares(agentId: string): Promise<AgentShare[]> {
  const { data } = await apiClient.get<AgentShare[]>(`/agents/${agentId}/shares`);
  return data;
}

export async function shareAgent(agentId: string, userId: string, role: ShareRole): Promise<AgentShare> {
  const { data } = await apiClient.post<AgentShare>(`/agents/${agentId}/shares`, { user_id: userId, role });
  return data;
}

export async function updateShareRole(agentId: string, shareId: string, role: ShareRole): Promise<AgentShare> {
  const { data } = await apiClient.patch<AgentShare>(`/agents/${agentId}/shares/${shareId}`, { role });
  return data;
}

export async function revokeShare(agentId: string, shareId: string): Promise<void> {
  await apiClient.delete(`/agents/${agentId}/shares/${shareId}`);
}
