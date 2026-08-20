import { useEffect, useRef, useState, type FormEvent } from "react";
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
  const sendMessage = useSendMessage(agentId ?? "");

  const [question, setQuestion] = useState("");
  const [sendError, setSendError] = useState<string | null>(null);
  const questionInputRef = useRef<HTMLInputElement>(null);

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

  // No bulk-delete endpoint exists — this composes the same single-conversation delete used
  // above, once per existing conversation, rather than adding any new backend behavior.
  async function handleDeleteAll() {
    if (!conversations || conversations.length === 0) return;
    if (!window.confirm("Delete all conversations? This cannot be undone.")) return;
    for (const conv of conversations) {
      await deleteConversation.mutateAsync(conv.id);
    }
    setActiveConversationId(null);
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
      await sendMessage.mutateAsync({ conversationId, question: text });
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
          {conversations && conversations.length > 0 && (
            <div className="border-t border-border p-2">
              <button
                type="button"
                onClick={handleDeleteAll}
                className="flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-xs text-ink-muted hover:text-danger"
              >
                <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                  <path
                    d="M3 4.5h10M6.5 4.5V3a1 1 0 0 1 1-1h1a1 1 0 0 1 1 1v1.5M4.5 4.5v8a1.5 1.5 0 0 0 1.5 1.5h4a1.5 1.5 0 0 0 1.5-1.5v-8"
                    stroke="currentColor"
                    strokeWidth="1.3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                Delete all conversations
              </button>
            </div>
          )}
        </aside>

        {/* Conversation */}
        <div className="flex flex-1 flex-col">
          <div className="flex-1 overflow-y-auto p-6">
            {!activeConversationId && (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <svg
                  width="28"
                  height="28"
                  viewBox="0 0 24 24"
                  fill="none"
                  aria-hidden="true"
                  className="mb-3 text-ink-muted"
                >
                  <path
                    d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8a2.5 2.5 0 0 1-2.5 2.5H9l-4 4v-4H6.5A2.5 2.5 0 0 1 4 13.5v-8Z"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinejoin="round"
                  />
                </svg>
                <h2 className="text-lg font-semibold text-ink">Start a conversation</h2>
                <p className="mt-1 max-w-sm text-sm text-ink-muted">
                  Ask anything about your data. I'll help you find insights, run queries, and answer your questions.
                </p>
                <button
                  type="button"
                  onClick={() => questionInputRef.current?.focus()}
                  className="mt-4 rounded-md border border-border bg-surface px-4 py-2 text-sm font-medium text-ink hover:bg-canvas"
                >
                  Ask about your business data
                </button>
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
                ref={questionInputRef}
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
            <p className="mx-auto mt-2 max-w-3xl text-center text-[11px] text-ink-muted">
              Agent can make mistakes. Please verify important information.
            </p>
          </form>
        </div>
      </div>
    </AppShell>
  );
}
