import { apiClient } from "./client";

export interface Conversation {
  id: string;
  agent_id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  sql: string | null;
  result_data: string | null;
  error_message: string | null;
  response_type: "text" | "table" | "kpi" | "chart";
  input_tokens: number | null;
  output_tokens: number | null;
  created_at: string;
}

export async function listConversations(agentId: string): Promise<Conversation[]> {
  const { data } = await apiClient.get<Conversation[]>(`/agents/${agentId}/conversations`);
  return data;
}

export async function createConversation(agentId: string): Promise<Conversation> {
  const { data } = await apiClient.post<Conversation>(`/agents/${agentId}/conversations`);
  return data;
}

export async function deleteConversation(conversationId: string): Promise<void> {
  await apiClient.delete(`/conversations/${conversationId}`);
}

export async function listMessages(conversationId: string): Promise<ChatMessage[]> {
  const { data } = await apiClient.get<ChatMessage[]>(`/conversations/${conversationId}/messages`);
  return data;
}

export async function sendMessage(conversationId: string, question: string): Promise<ChatMessage> {
  const { data } = await apiClient.post<ChatMessage>(`/conversations/${conversationId}/messages`, { question });
  return data;
}
