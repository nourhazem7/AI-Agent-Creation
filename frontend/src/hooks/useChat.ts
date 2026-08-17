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

export function useSendMessage(agentId: string, conversationId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (question: string) => sendMessage(conversationId as string, question),
    onSuccess: () => {
      if (conversationId) queryClient.invalidateQueries({ queryKey: messagesKey(conversationId) });
      queryClient.invalidateQueries({ queryKey: conversationsKey(agentId) });
    },
  });
}
