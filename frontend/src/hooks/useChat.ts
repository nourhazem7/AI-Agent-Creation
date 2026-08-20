import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createConversation,
  deleteConversation,
  listConversations,
  listMessages,
  sendMessage,
} from "../api/chat";

const conversationsKey = (agentId: string) => ["conversations", agentId] as const;
const messagesKey = (conversationId: string) => ["messages", conversationId] as const;

export function useConversations(agentId: string) {
  return useQuery({ queryKey: conversationsKey(agentId), queryFn: () => listConversations(agentId) });
}

export function useCreateConversation(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => createConversation(agentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: conversationsKey(agentId) }),
  });
}

export function useDeleteConversation(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (conversationId: string) => deleteConversation(conversationId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: conversationsKey(agentId) }),
  });
}

export function useMessages(conversationId: string | null) {
  return useQuery({
    queryKey: messagesKey(conversationId ?? ""),
    queryFn: () => listMessages(conversationId as string),
    enabled: !!conversationId,
  });
}

export function useSendMessage(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    // conversationId is taken per-call (not baked into the hook at render time) — sending the
    // very first message of a brand-new conversation creates it and sends in the same action,
    // so the id used here must always be the one just resolved by the caller, never a value
    // closed over from a stale prior render (that mismatch was the "Conversation not found" bug).
    mutationFn: ({ conversationId, question }: { conversationId: string; question: string }) =>
      sendMessage(conversationId, question),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: messagesKey(variables.conversationId) });
      queryClient.invalidateQueries({ queryKey: conversationsKey(agentId) });
    },
  });
}
