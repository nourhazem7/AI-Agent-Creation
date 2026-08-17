import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { AppShell } from "../components/layout/AppShell";
import { MessageBubble } from "../components/chat/MessageBubble";
import { Button, StatusIndicator } from "../components/ui";
import { useAgent } from "../hooks/useAgents";
import {
  useConversations,
  useCreateConversation,
  useDeleteConversation,
  useMessages,
  useSendMessage,
} from "../hooks/useChat";
import { apiErrorMessage } from "../api/client";

export default function ChatPage() {
  const { agentId } = useParams<{ agentId: string }>();
  const { data: agent, isError: agentError, isLoading: agentLoading } = useAgent(agentId);
  const { data: conversations, isLoading: conversationsLoading } = useConversations(agentId ?? "");
  const createConversation = useCreateConversation(agentId ?? "");
  const deleteConversation = useDeleteConversation(agentId ?? "");

  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const { data: messages, isLoading: messagesLoading } = useMessages(activeConversationId);
  const sendMessage = useSendMessage(agentId ?? "", activeConversationId);

  const [question, setQuestion] = useState("");
  const [sendError, setSendError] = useState<string | null>(null);

  // Select the most recent conversation once loaded; otherwise nothing is selected yet.
  useEffect(() => {
    if (!activeConversationId && conversations && conversations.length > 0) {
      setActiveConversationId(conversations[0].id);
    }
  }, [conversations, activeConversationId]);

  async function handleNewChat() {
    const conversation = await createConversation.mutateAsync();
    setActiveConversationId(conversation.id);
  }

  async function handleDelete(conversationId: string) {
    await deleteConversation.mutateAsync(conversationId);
    if (activeConversationId === conversationId) setActiveConversationId(null);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    setSendError(null);

    let conversationId = activeConversationId;
    if (!conversationId) {
      const conversation = await createConversation.mutateAsync();
      conversationId = conversation.id;
      setActiveConversationId(conversationId);
    }

    const text = question;
    setQuestion("");
    try {
      await sendMessage.mutateAsync(text);
    } catch (err) {
      setSendError(apiErrorMessage(err, "Could not send that message."));
    }
  }

  if (!agentId) return null;

  if (agentLoading) {
    return (
      <AppShell>
        <div className="flex h-[calc(100vh-3.5rem)] items-center justify-center">
          <span
            className="h-6 w-6 animate-spin rounded-full border-2 border-ink border-t-transparent"
            aria-label="Loading agent"
          />
        </div>
      </AppShell>
    );
  }

  if (agentError || !agent) {
    return (
      <AppShell>
        <div className="flex h-[calc(100vh-3.5rem)] flex-col items-center justify-center gap-3 text-center">
          <h1 className="text-lg font-semibold text-ink">Agent not found</h1>
          <p className="max-w-sm text-sm text-ink-muted">
            This agent may have been deleted, or you don't have access to it.
          </p>
          <Link to="/" className="text-sm font-medium text-ink underline underline-offset-2">
            Back to Dashboard
          </Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell
      headerExtra={
        agent ? (
          <span className="hidden items-center gap-2 text-sm text-ink-muted sm:flex">
            {agent.name}
            <StatusIndicator status={agent.status === "active" ? "success" : "idle"} label="Connected" />
          </span>
        ) : undefined
      }
    >
      <div className="flex h-[calc(100vh-3.5rem)]">
        {/* Conversation sidebar */}
        <aside className="flex w-64 shrink-0 flex-col border-r border-border bg-surface">
          <div className="p-3">
            <Button className="w-full" onClick={handleNewChat} isLoading={createConversation.isPending}>
              New Chat
            </Button>
          </div>
          <div className="flex-1 overflow-y-auto px-2 pb-2">
            {conversationsLoading && <p className="px-2 py-2 text-xs text-ink-muted">Loading…</p>}
            {conversations?.map((conv) => (
              <div
                key={conv.id}
                className={`group flex items-center justify-between gap-1 rounded-md px-2 py-2 text-sm
                  ${conv.id === activeConversationId ? "bg-canvas text-ink" : "text-ink-muted hover:bg-canvas"}`}
              >
                <button
                  type="button"
                  onClick={() => setActiveConversationId(conv.id)}
                  className="flex-1 truncate text-left"
                >
                  {conv.title}
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(conv.id)}
                  className="opacity-0 group-hover:opacity-100 text-ink-muted hover:text-danger"
                  aria-label="Delete conversation"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </aside>

        {/* Conversation */}
        <div className="flex flex-1 flex-col">
          <div className="flex-1 overflow-y-auto p-6">
            {!activeConversationId && (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <h2 className="text-lg font-semibold text-ink">Ask about your business data</h2>
                <p className="mt-1 max-w-sm text-sm text-ink-muted">
                  Try: "Which department had the highest number of employees?"
                </p>
              </div>
            )}
            {activeConversationId && messagesLoading && (
              <p className="text-sm text-ink-muted">Loading…</p>
            )}
            <div className="mx-auto flex max-w-3xl flex-col gap-4">
              {messages?.map((m) => (
                <MessageBubble key={m.id} message={m} />
              ))}
              {sendMessage.isPending && (
                <div className="flex justify-start">
                  <div className="rounded-lg border border-border bg-surface px-4 py-3">
                    <StatusIndicator status="pending" label="Analyzing your question…" />
                  </div>
                </div>
              )}
            </div>
          </div>

          <form onSubmit={handleSubmit} className="border-t border-border bg-surface p-4">
            <div className="mx-auto flex max-w-3xl gap-2">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask about your business data…"
                className="flex-1 rounded-md border border-border bg-canvas px-3 py-2 text-sm text-ink
                  placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-ink/20"
              />
              <Button type="submit" isLoading={sendMessage.isPending} disabled={!question.trim()}>
                Send
              </Button>
            </div>
            {sendError && <p className="mx-auto mt-2 max-w-3xl text-sm text-danger">{sendError}</p>}
          </form>
        </div>
      </div>
    </AppShell>
  );
}
