import { CheckCircle2, CircleSlash, FileText, PiggyBank, ReceiptText, Sparkles, Wallet } from "lucide-react";
import { Link } from "react-router-dom";
import { useAuth } from "../../lib/auth";
import { fmtDate, money, num } from "../../lib/format";
import type { ChatCard } from "../../types";
import { Badge, Button, ProgressBar } from "../ui";

function Frame({ icon, title, children, tone = "neutral" }: { icon: React.ReactNode; title: string; children: React.ReactNode; tone?: "neutral" | "gold" | "success" | "muted" }) {
  const border = { neutral: "border-line", gold: "border-gold/50", success: "border-success/40", muted: "border-line opacity-80" }[tone];
  return (
    <div className={`mt-2 overflow-hidden rounded-lg border bg-bg/60 ${border}`}>
      <div className="flex items-center gap-2 border-b border-line/70 bg-bg2/50 px-3 py-2 text-[11px] font-medium uppercase tracking-[0.16em] text-muted">
        <span className="text-gold">{icon}</span>{title}
      </div>
      <div className="px-3 py-2.5 text-[13px]">{children}</div>
    </div>
  );
}

function Fields({ fields }: { fields: Record<string, unknown> }) {
  return (
    <dl className="grid grid-cols-[auto,1fr] gap-x-4 gap-y-1">
      {Object.entries(fields).map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-muted">{k}</dt>
          <dd className="text-right font-medium text-ink tabular">{String(v ?? "—")}</dd>
        </div>
      ))}
    </dl>
  );
}

export function ConfirmationCard({ card, onDecide, busy }: { card: ChatCard; onDecide: (id: string, ok: boolean) => void; busy: boolean }) {
  const { user } = useAuth();
  const cur = user?.currency || "INR";
  const s = card.summary || {};
  const pending = card.status === "pending";
  const destructive = String(card.action).startsWith("delete");
  const record = s.record as Record<string, string> | undefined;
  return (
    <Frame icon={<Sparkles className="h-3.5 w-3.5" />} title={s.title || "Confirm action"} tone={pending ? "gold" : "muted"}>
      {record && (
        <div className="mb-2 rounded-md border border-line/70 bg-card px-2.5 py-2">
          {"description" in record ? (
            <div className="flex justify-between gap-3">
              <span className="truncate">{record.description}<span className="block text-[11px] text-muted">{record.category} · {record.date && fmtDate(record.date)}</span></span>
              <span className="tabular font-medium">{money(record.amount, cur)}</span>
            </div>
          ) : (
            <div className="flex justify-between gap-3"><span>{record.name}</span><span className="tabular">{money(record.current_amount, cur)} / {money(record.target_amount, cur)}</span></div>
          )}
        </div>
      )}
      {s.fields && <Fields fields={s.fields} />}
      {s.changes && <><p className="mb-1 text-[11px] uppercase tracking-wider text-muted">Changes</p><Fields fields={s.changes} /></>}
      {s.warning && <p className="mt-2 text-[12px] text-danger">{s.warning}</p>}
      {pending ? (
        <div className="mt-3 flex gap-2">
          <Button size="sm" variant={destructive ? "danger" : "primary"} disabled={busy} onClick={() => onDecide(card.confirmation_id, true)}>
            <CheckCircle2 className="h-3.5 w-3.5" /> {destructive ? "Confirm delete" : "Confirm"}
          </Button>
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => onDecide(card.confirmation_id, false)}>Cancel</Button>
        </div>
      ) : (
        <p className="mt-2 flex items-center gap-1.5 text-[12px] text-muted"><CircleSlash className="h-3.5 w-3.5" /> {card.status === "confirmed" ? "Confirmed" : card.status === "cancelled" ? "Cancelled" : "No longer pending"}</p>
      )}
    </Frame>
  );
}

export function ResultCard({ card }: { card: ChatCard }) {
  const { user } = useAuth();
  const cur = user?.currency || "INR";
  const r = card.record || {};
  const icon = card.type === "budget_result" ? <Wallet className="h-3.5 w-3.5" /> : card.type === "savings_result" ? <PiggyBank className="h-3.5 w-3.5" /> : <ReceiptText className="h-3.5 w-3.5" />;
  const label = { created: "Saved", updated: "Updated", deleted: "Deleted", contribution: "Contribution recorded" }[card.operation as string] || "Done";
  return (
    <Frame icon={icon} title={label} tone="success">
      {card.type === "transaction_result" && (
        <div className="flex justify-between gap-3">
          <span>{r.description}<span className="block text-[11px] text-muted">{r.category} · {fmtDate(r.date)}</span></span>
          <span className={`tabular font-medium ${r.type === "income" ? "text-success" : ""}`}>{r.type === "income" ? "+" : "−"}{money(r.amount, cur)}</span>
        </div>
      )}
      {card.type === "budget_result" && <div className="flex justify-between"><span>{r.category} · {fmtDate(r.month, "month")}</span><span className="tabular font-medium">{money(r.amount, cur)}</span></div>}
      {card.type === "savings_result" && (
        <div>
          <div className="mb-1.5 flex justify-between"><span>{r.name}</span><span className="tabular">{money(r.current_amount, cur)} / {money(r.target_amount, cur)}</span></div>
          <ProgressBar value={num(r.progress_percent)} tone="gold" label={`${r.name} progress`} />
        </div>
      )}
    </Frame>
  );
}

export function DataCard({ card }: { card: ChatCard }) {
  const { user } = useAuth();
  const cur = user?.currency || "INR";
  if (card.type === "transactions") {
    const items = (card.items || []) as Record<string, string>[];
    if (!items.length) return <Frame icon={<ReceiptText className="h-3.5 w-3.5" />} title="Transactions">No matching transactions.</Frame>;
    return (
      <Frame icon={<ReceiptText className="h-3.5 w-3.5" />} title={`Transactions · ${card.total} found`}>
        <ul className="divide-y divide-line/60">
          {items.slice(0, 8).map((t) => (
            <li key={t.id} className="flex justify-between gap-3 py-1.5">
              <span className="min-w-0"><span className="block truncate">{t.description}</span><span className="text-[11px] text-muted">{t.category} · {fmtDate(t.date)}</span></span>
              <span className={`tabular shrink-0 ${t.type === "income" ? "text-success" : ""}`}>{t.type === "income" ? "+" : "−"}{money(t.amount, cur)}</span>
            </li>
          ))}
        </ul>
        {items.length > 8 && <Link to="/app/transactions" className="mt-1 block text-[12px] text-gold hover:underline">View all in Transactions →</Link>}
      </Frame>
    );
  }
  if (card.type === "budgets") {
    const items = (card.items || []) as Record<string, any>[]; // eslint-disable-line @typescript-eslint/no-explicit-any
    return (
      <Frame icon={<Wallet className="h-3.5 w-3.5" />} title={`Budgets · ${fmtDate(card.month, "month")}`}>
        {!items.length ? "No budgets match." : (
          <ul className="space-y-2.5">
            {items.map((b) => (
              <li key={b.id}>
                <div className="mb-1 flex justify-between gap-2"><span>{b.category.name}</span><span className="tabular text-muted">{money(b.spent, cur)} / {money(b.amount, cur)}</span></div>
                <ProgressBar value={num(b.utilization)} tone={b.status === "exceeded" ? "danger" : b.status === "at_risk" ? "warning" : "forest"} />
              </li>
            ))}
          </ul>
        )}
      </Frame>
    );
  }
  if (card.type === "goals") {
    const items = (card.items || []) as Record<string, string>[];
    return (
      <Frame icon={<PiggyBank className="h-3.5 w-3.5" />} title="Savings goals">
        {!items.length ? "No savings goals yet." : (
          <ul className="space-y-3">
            {items.map((g) => (
              <li key={g.id}>
                <div className="mb-1 flex justify-between gap-2"><span>{g.name}</span><span className="tabular text-muted">{g.progress_percent}%</span></div>
                <ProgressBar value={num(g.progress_percent)} tone="gold" />
                <p className="mt-1 text-[11px] text-muted">{money(g.remaining_amount, cur)} to go{g.required_monthly ? ` · ${money(g.required_monthly, cur)}/month` : ""}</p>
              </li>
            ))}
          </ul>
        )}
      </Frame>
    );
  }
  if (card.type === "summary" || card.type === "analysis") {
    const d = card.data || {};
    const s = card.type === "summary" ? d : d.summary;
    const cats = (card.type === "summary" ? d.top : d.categories) || [];
    return (
      <Frame icon={<Sparkles className="h-3.5 w-3.5" />} title={`Summary · ${s.period_start ? fmtDate(s.period_start, "month") : ""}`}>
        <div className="grid grid-cols-3 gap-2 text-center">
          {[["Income", s.income], ["Expenses", s.expenses], ["Saved", s.savings]].map(([k, v]) => (
            <div key={k} className="rounded-md bg-card px-1 py-2"><p className="text-[10px] uppercase tracking-wider text-muted">{k}</p><p className="tabular font-serif text-[15px] font-semibold">{money(v, cur, { compact: true })}</p></div>
          ))}
        </div>
        {cats.length > 0 && (
          <ul className="mt-2.5 space-y-1">
            {cats.slice(0, 5).map((c: Record<string, string>) => (
              <li key={c.category} className="flex justify-between"><span className="text-muted">{c.category}</span><span className="tabular">{money(c.amount, cur)}{c.share ? <span className="ml-1.5 text-[11px] text-muted">{c.share}%</span> : null}</span></li>
            ))}
          </ul>
        )}
        {d.mom?.change_percent && <p className="mt-2 text-[12px] text-muted">Spending vs last month: <span className={num(d.mom.change) > 0 ? "text-danger" : "text-success"}>{num(d.mom.change) > 0 ? "+" : ""}{d.mom.change_percent}%</span></p>}
      </Frame>
    );
  }
  if (card.type === "recommendations") {
    const items = (card.items || []) as Record<string, any>[]; // eslint-disable-line @typescript-eslint/no-explicit-any
    return (
      <Frame icon={<Sparkles className="h-3.5 w-3.5" />} title={`Budget proposals · ${fmtDate(card.month, "month")}`}>
        {!items.length ? "Not enough history yet." : (
          <ul className="space-y-2">
            {items.slice(0, 6).map((r) => (
              <li key={r.id} className="flex items-center justify-between gap-2">
                <span>{r.category} <Badge tone={r.confidence === "high" ? "success" : r.confidence === "medium" ? "gold" : "neutral"}>{r.confidence}</Badge></span>
                <span className="tabular font-medium">{money(r.proposed_amount, cur)}</span>
              </li>
            ))}
          </ul>
        )}
        <Link to="/app/budgets" className="mt-2 block text-[12px] text-gold hover:underline">Review and approve on the Budgets page →</Link>
      </Frame>
    );
  }
  if (card.type === "report") {
    return (
      <Frame icon={<FileText className="h-3.5 w-3.5" />} title={`${card.report_type} report · ${card.period}`}>
        <Fields fields={{ Income: money(card.summary.income, cur), Expenses: money(card.summary.expenses, cur), Savings: money(card.summary.savings, cur), "Savings rate": `${card.summary.savings_rate}%` }} />
        <Link to="/app/reports" className="mt-2 block text-[12px] text-gold hover:underline">Download PDF or CSV in Reports →</Link>
      </Frame>
    );
  }
  return null;
}
