import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../lib/api";
import { useInvalidateFinance } from "../../lib/queries";
import type { ChatMessage } from "../../types";

type ChatResponse = { conversation_id: string; message: ChatMessage };
const CONV_KEY = "fm-jocasta-conversation";

/** Shared chat state for the floating panel and the full JOCASTA page. */
export function useJocasta(initialConversationId?: string | null) {
  const [conversationId, setConversationId] = useState<string | null>(() => {
    if (initialConversationId !== undefined) return initialConversationId;
    try { return sessionStorage.getItem(CONV_KEY); } catch { return null; }
  });
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const invalidate = useInvalidateFinance();
  const loadedFor = useRef<string | null>(null);

  useEffect(() => {
    try { if (conversationId) sessionStorage.setItem(CONV_KEY, conversationId); } catch { /* ignore */ }
    if (!conversationId || loadedFor.current === conversationId) return;
    loadedFor.current = conversationId;
    setLoadingHistory(true);
    api<ChatMessage[]>(`/assistant/conversations/${conversationId}/messages`)
      .then(setMessages)
      .catch(() => { setConversationId(null); setMessages([]); })
      .finally(() => setLoadingHistory(false));
  }, [conversationId]);

  const absorb = useCallback((r: ChatResponse) => {
    loadedFor.current = r.conversation_id;
    setConversationId(r.conversation_id);
    const resolved = r.message.meta && (r.message.meta as { resolved_confirmation?: { id: string; status: string } }).resolved_confirmation;
    setMessages((prev) => {
      const next = prev.filter((m) => !m.pending).map((m) => resolved ? markResolved(m, resolved.id, resolved.status) : m);
      return [...next, r.message];
    });
    const cards = r.message.meta?.cards || [];
    if (cards.some((c) => c.type.endsWith("_result") || c.type === "report" || c.type === "recommendations")) invalidate();
  }, [invalidate]);

  const send = useCallback(async (text: string) => {
    const t = text.trim();
    if (!t || sending) return;
    setError(null);
    const optimistic: ChatMessage = { id: `local-${Date.now()}`, role: "user", content: t, created_at: new Date().toISOString() };
    setMessages((m) => [...m, optimistic]);
    setSending(true);
    try {
      const r = await api<ChatResponse>("/assistant/chat", { body: { message: t, conversation_id: conversationId }, timeoutMs: 90000 });
      setMessages((m) => m.map((x) => (x.id === optimistic.id ? { ...x, id: `u-${r.message.id}` } : x)));
      absorb(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "JOCASTA is unavailable right now.");
    } finally {
      setSending(false);
    }
  }, [absorb, conversationId, sending]);

  const decide = useCallback(async (confirmationId: string, approve: boolean) => {
    setError(null);
    setSending(true);
    try {
      const r = await api<ChatResponse>(`/assistant/confirmations/${confirmationId}/${approve ? "confirm" : "cancel"}`, { method: "POST" });
      absorb(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not complete the action.");
      setMessages((prev) => prev.map((m) => markResolved(m, confirmationId, "resolved")));
    } finally {
      setSending(false);
    }
  }, [absorb]);

  const reset = useCallback(() => {
    loadedFor.current = null;
    setConversationId(null);
    setMessages([]);
    setError(null);
    try { sessionStorage.removeItem(CONV_KEY); } catch { /* ignore */ }
  }, []);

  return { conversationId, setConversationId, messages, send, decide, sending, loadingHistory, error, reset };
}

function markResolved(m: ChatMessage, id: string, status: string): ChatMessage {
  if (!m.meta?.cards?.some((c) => c.confirmation_id === id)) return m;
  return { ...m, meta: { ...m.meta, cards: m.meta.cards.map((c) => (c.confirmation_id === id ? { ...c, status } : c)) } };
}
