import { apiClient } from "./client";

export interface AgentMemory {
  id: string;
  agent_id: string;
  content: string;
  created_at: string;
  updated_at: string;
}

export async function listAgentMemory(agentId: string): Promise<AgentMemory[]> {
  const { data } = await apiClient.get<AgentMemory[]>(`/agents/${agentId}/memory`);
  return data;
}

export async function createAgentMemory(agentId: string, content: string): Promise<AgentMemory> {
  const { data } = await apiClient.post<AgentMemory>(`/agents/${agentId}/memory`, { content });
  return data;
}

export async function deleteAgentMemory(agentId: string, memoryId: string): Promise<void> {
  await apiClient.delete(`/agents/${agentId}/memory/${memoryId}`);
}
