import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquarePlus, Trash2 } from "lucide-react";
import { ChatView, JocastaAvatar } from "../components/jocasta/ChatView";
import { useJocasta } from "../components/jocasta/useJocasta";
import { cx } from "../components/ui";
import { api } from "../lib/api";
import { fmtDate } from "../lib/format";
import type { Conversation } from "../types";

export default function JocastaPage() {
  const chat = useJocasta();
  const qc = useQueryClient();
  const convs = useQuery({ queryKey: ["conversations", chat.conversationId, chat.messages.length > 0], queryFn: () => api<Conversation[]>("/assistant/conversations") });
  const remove = async (id: string) => {
    await api(`/assistant/conversations/${id}`, { method: "DELETE" });
    if (id === chat.conversationId) chat.reset();
    qc.invalidateQueries({ queryKey: ["conversations"] });
  };
  return (
    <div className="-mx-4 -mb-28 -mt-8 grid h-[calc(100vh-4rem)] sm:-mx-8 lg:grid-cols-[280px,1fr]">
      <aside className="hidden flex-col border-r border-line bg-bg2/40 lg:flex">
        <div className="flex items-center gap-3 border-b border-line px-5 py-5">
          <JocastaAvatar size={40} />
          <div><p className="font-serif text-xl tracking-[0.12em]">JOCASTA</p><p className="text-[10px] uppercase tracking-[0.2em] text-gold">Multi-agent assistant</p></div>
        </div>
        <button onClick={chat.reset} className="mx-4 mt-4 flex items-center justify-center gap-2 rounded-md border border-line bg-card py-2 text-sm hover:border-gold/60"><MessageSquarePlus className="h-4 w-4" /> New conversation</button>
        <p className="eyebrow mx-5 mb-2 mt-6">History</p>
        <ul className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-4">
          {(convs.data || []).map((c) => (
            <li key={c.id} className="group flex items-center">
              <button onClick={() => chat.setConversationId(c.id)} className={cx("min-w-0 flex-1 rounded-md px-3 py-2 text-left text-sm transition", c.id === chat.conversationId ? "bg-card shadow-soft" : "hover:bg-card/60")}>
                <span className="block truncate">{c.title}</span><span className="text-[11px] text-muted">{fmtDate(c.updated_at)}</span>
              </button>
              <button onClick={() => remove(c.id)} className="p-1.5 text-muted opacity-0 hover:text-danger group-hover:opacity-100" aria-label={`Delete conversation ${c.title}`}><Trash2 className="h-3.5 w-3.5" /></button>
            </li>
          ))}
          {!convs.data?.length && <li className="px-3 text-xs text-muted">Conversations will appear here.</li>}
        </ul>
      </aside>
      <section className="flex min-h-0 flex-col">
        <div className="flex items-center justify-between border-b border-line px-4 py-3 lg:hidden">
          <span className="font-serif text-lg tracking-[0.12em]">JOCASTA</span>
          <button onClick={chat.reset} className="text-xs text-gold">New conversation</button>
        </div>
        <div className="mx-auto flex min-h-0 w-full max-w-3xl flex-1 flex-col"><ChatView chat={chat} /></div>
      </section>
    </div>
  );
}
