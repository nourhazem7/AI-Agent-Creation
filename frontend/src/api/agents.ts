import { apiClient } from "./client";
import type { Agent } from "../types";

export interface CreateAgentPayload {
  name: string;
  description?: string;
  llm_model?: string;
  custom_instructions?: string;
}

export async function listAgents(): Promise<Agent[]> {
  const { data } = await apiClient.get<Agent[]>("/agents");
  return data;
}

export async function getAgent(agentId: string): Promise<Agent> {
  const { data } = await apiClient.get<Agent>(`/agents/${agentId}`);
  return data;
}

export async function createAgent(payload: CreateAgentPayload): Promise<Agent> {
  const { data } = await apiClient.post<Agent>("/agents", payload);
  return data;
}

export interface UpdateAgentPayload {
  name?: string;
  description?: string;
}

export async function updateAgent(agentId: string, payload: UpdateAgentPayload): Promise<Agent> {
  const { data } = await apiClient.patch<Agent>(`/agents/${agentId}`, payload);
  return data;
}

export async function deleteAgent(agentId: string): Promise<void> {
  await apiClient.delete(`/agents/${agentId}`);
}
