import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, ArrowUp, Loader2, Wrench } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import type { ChatMessage } from "../../types";
import { cx } from "../ui";
import { ConfirmationCard, DataCard, ResultCard } from "./Cards";
import type { useJocasta } from "./useJocasta";

const TOOL_LABEL: Record<string, string> = {
  create_transaction: "Preparing transaction", list_transactions: "Searching transactions", get_transaction: "Reading transaction",
  update_transaction: "Preparing update", delete_transaction: "Preparing deletion", create_budget: "Preparing budget", list_budgets: "Reading budgets",
  update_budget: "Preparing budget change", delete_budget: "Preparing budget removal", create_savings_goal: "Preparing goal", list_savings_goals: "Reading goals",
  update_savings_goal: "Preparing goal change", delete_savings_goal: "Preparing goal removal", record_savings_contribution: "Preparing contribution",
  get_financial_summary: "Calculating summary", analyze_spending: "Analysing spending", calculate_budget_recommendation: "Computing recommendations",
  generate_financial_report: "Generating report", suggest_category: "Categorising",
};

export function JocastaAvatar({ size = 32 }: { size?: number }) {
  return (
    <span className="grid shrink-0 place-items-center rounded-full border border-gold/60 bg-forest text-[#E9E1D2]" style={{ width: size, height: size }} aria-hidden>
      <span className="font-serif italic" style={{ fontSize: size * 0.5, lineHeight: 1 }}>J</span>
    </span>
  );
}

function Typing() {
  return (
    <div className="flex items-center gap-3" aria-live="polite" aria-label="JOCASTA is thinking">
      <JocastaAvatar size={28} />
      <div className="flex items-center gap-1 rounded-2xl rounded-tl-sm border border-line bg-card px-4 py-3">
        {[0, 1, 2].map((i) => (
          <motion.span key={i} className="h-1.5 w-1.5 rounded-full bg-gold" animate={{ opacity: [0.25, 1, 0.25], y: [0, -2, 0] }} transition={{ duration: 1.1, repeat: Infinity, delay: i * 0.15 }} />
        ))}
        <span className="ml-2 text-xs italic text-muted">consulting your ledger…</span>
      </div>
    </div>
  );
}

function Bubble({ m, onDecide, busy }: { m: ChatMessage; onDecide: (id: string, ok: boolean) => void; busy: boolean }) {
  const mine = m.role === "user";
  const cards = m.meta?.cards || [];
  const events = (m.meta?.tool_events || []).filter((e) => e.status !== "rejected");
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className={cx("flex gap-3", mine && "justify-end")}>
      {!mine && <JocastaAvatar size={28} />}
      <div className={cx("max-w-[86%] sm:max-w-[78%]", mine && "text-right")}>
        <div className={cx("inline-block whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-left text-[14px] leading-relaxed",
          mine ? "rounded-tr-sm bg-forest text-onforest" : "rounded-tl-sm border border-line bg-card text-ink",
          m.meta?.error && "border-danger/40")}>
          {m.meta?.error && <AlertTriangle className="mr-1.5 inline h-3.5 w-3.5 text-danger" />}
          {m.content}
        </div>
        {!mine && events.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {events.map((e, i) => (
              <span key={i} className={cx("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10.5px]", e.status === "error" ? "border-danger/30 text-danger" : "border-line text-muted")}>
                <Wrench className="h-2.5 w-2.5" /> {TOOL_LABEL[e.tool] || e.tool}{e.status === "error" ? " · failed" : ""}
              </span>
            ))}
          </div>
        )}
        {!mine && cards.map((c, i) => (
          <div key={i} className="text-left">
            {c.type === "confirmation" ? <ConfirmationCard card={c} onDecide={onDecide} busy={busy} />
              : c.type.endsWith("_result") ? <ResultCard card={c} /> : <DataCard card={c} />}
          </div>
        ))}
      </div>
    </motion.div>
  );
}

export function ChatView({ chat, compact = false }: { chat: ReturnType<typeof useJocasta>; compact?: boolean }) {
  const [text, setText] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const { data: status } = useQuery({ queryKey: ["assistant-status"], queryFn: () => api<{ available: boolean; model: string | null }>("/assistant/status"), staleTime: 60_000 });
  const { data: sugg } = useQuery({ queryKey: ["assistant-suggestions"], queryFn: () => api<{ suggestions: string[] }>("/assistant/suggestions"), staleTime: Infinity });

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [chat.messages.length, chat.sending]);

  const submit = (t = text) => {
    if (!t.trim()) return;
    chat.send(t);
    setText("");
    inputRef.current?.focus();
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className={cx("flex-1 space-y-4 overflow-y-auto", compact ? "px-4 py-4" : "px-2 py-6 sm:px-6")} aria-live="polite">
        {status && !status.available && (
          <div className="rounded-lg border border-gold/40 bg-gold/5 px-3 py-2 text-[12.5px] text-ink">
            JOCASTA's language model is not configured on the server (GROQ_API_KEY). Other features still work.
          </div>
        )}
        {chat.loadingHistory && <div className="flex justify-center py-6"><Loader2 className="h-5 w-5 animate-spin text-gold" /></div>}
        {!chat.loadingHistory && chat.messages.length === 0 && (
          <div className="flex flex-col items-center py-4 text-center">
            <JocastaAvatar size={compact ? 44 : 56} />
            <p className={cx("mx-auto mt-4 font-serif text-ink", compact ? "text-xl" : "text-3xl")}>Good {greeting()}. How may I help with your finances?</p>
            <p className="mx-auto mt-2 max-w-sm text-sm text-muted">I can record transactions, manage budgets and savings goals, and explain your spending — always from your actual records.</p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              {(sugg?.suggestions || []).slice(0, compact ? 4 : 8).map((s) => (
                <button key={s} onClick={() => submit(s)} className="rounded-full border border-line bg-card px-3 py-1.5 text-[12.5px] text-ink transition hover:border-gold/60 hover:text-gold">{s}</button>
              ))}
            </div>
          </div>
        )}
        {chat.messages.map((m) => <Bubble key={m.id} m={m} onDecide={chat.decide} busy={chat.sending} />)}
        <AnimatePresence>{chat.sending && <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}><Typing /></motion.div>}</AnimatePresence>
        {chat.error && (
          <div role="alert" className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-[13px] text-danger">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {chat.error}
          </div>
        )}
        <div ref={endRef} />
      </div>
      {chat.messages.length > 0 && !chat.sending && (
        <div className="flex gap-2 overflow-x-auto px-4 pb-2 [scrollbar-width:none]">
          {["Show my last five expenses", "Analyze my spending this month", "Which budgets are exceeded?"].map((s) => (
            <button key={s} onClick={() => submit(s)} className="shrink-0 rounded-full border border-line px-2.5 py-1 text-[11.5px] text-muted hover:border-gold/60 hover:text-gold">{s}</button>
          ))}
        </div>
      )}
      <form onSubmit={(e) => { e.preventDefault(); submit(); }} className="border-t border-line bg-card/70 p-3">
        <div className="flex items-end gap-2 rounded-xl border border-line bg-card px-3 py-2 focus-within:border-gold/70 focus-within:ring-2 focus-within:ring-gold/15">
          <label htmlFor="jocasta-input" className="sr-only">Message JOCASTA</label>
          <textarea id="jocasta-input" ref={inputRef} rows={1} value={text} maxLength={2000} placeholder="Ask JOCASTA… e.g. “Add ₹500 for groceries today”"
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
            className="max-h-32 min-h-[24px] flex-1 resize-none bg-transparent py-1 text-sm text-ink placeholder:text-muted/70 focus:outline-none" />
          <button type="submit" disabled={!text.trim() || chat.sending} aria-label="Send message"
            className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-forest text-onforest transition disabled:opacity-40">
            {chat.sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowUp className="h-4 w-4" />}
          </button>
        </div>
        <p className="mt-1.5 px-1 text-[10.5px] text-muted">JOCASTA asks before changing records. Not investment advice.</p>
      </form>
    </div>
  );
}

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "morning" : h < 17 ? "afternoon" : "evening";
}
