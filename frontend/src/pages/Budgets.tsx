import { Check, Copy, Pencil, Plus, Sparkles, Trash2, Wallet, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge, Button, Card, ConfirmDialog, EmptyState, ErrorState, Input, Modal, PageHeader, ProgressBar, Select, Skeleton, errMsg, useToast } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate, money, monthKey, num, shiftMonth } from "../lib/format";
import { useBudgets, useCategories, useFinanceMutation, useRecommendations } from "../lib/queries";
import type { BudgetRow, Recommendation } from "../types";
import { MonthSwitcher } from "./Overview";

const STATUS = { on_track: ["On track", "success"], at_risk: ["At risk", "warning"], exceeded: ["Exceeded", "danger"] } as const;

function BudgetModal({ open, onClose, month, budget, existing }: { open: boolean; onClose: () => void; month: string; budget: BudgetRow | null; existing: string[] }) {
  const { data: cats } = useCategories();
  const toast = useToast();
  const [categoryId, setCategoryId] = useState("");
  const [amount, setAmount] = useState("");
  const [notes, setNotes] = useState("");
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { if (open) { setCategoryId(budget?.category.id || ""); setAmount(budget?.amount || ""); setNotes(budget?.notes || ""); setErr(null); } }, [open, budget]);
  const save = useFinanceMutation(() => budget
    ? api(`/budgets/${budget.id}`, { method: "PATCH", body: { amount, notes: notes || null } })
    : api("/budgets", { body: { category_id: categoryId, month, amount, notes: notes || null } }));
  const submit = async () => {
    if (!budget && !categoryId) return setErr("Choose a category");
    if (!/^\d{1,12}(\.\d{1,2})?$/.test(amount) || Number(amount) <= 0) return setErr("Enter a positive amount");
    try { await save.mutateAsync(); toast.success(budget ? "Budget updated" : "Budget created"); onClose(); } catch (e) { setErr(errMsg(e)); }
  };
  return (
    <Modal open={open} onClose={onClose} title={budget ? `Edit ${budget.category.name} budget` : `New budget · ${fmtDate(month, "month")}`}
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button onClick={submit} loading={save.isPending}>Save budget</Button></>}>
      <div className="space-y-4">
        {!budget && (
          <Select label="Category" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            <option value="">Choose…</option>
            {(cats || []).filter((c) => c.kind !== "income" && !existing.includes(c.id)).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
        )}
        <Input label="Monthly amount" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="4000" />
        <Input label="Notes (optional)" value={notes} onChange={(e) => setNotes(e.target.value)} />
        {err && <p role="alert" className="text-sm text-danger">{err}</p>}
      </div>
    </Modal>
  );
}

function RecommendationCard({ r, cur }: { r: Recommendation; cur: string }) {
  const toast = useToast();
  const [amount, setAmount] = useState(r.proposed_amount);
  const [editing, setEditing] = useState(false);
  const decide = useFinanceMutation((approve: boolean) => api(`/budgets/recommendations/${r.id}/decision`, { body: { approve, amount: approve && amount !== r.proposed_amount ? amount : null } }));
  const b = r.historical_basis;
  const go = async (approve: boolean) => {
    try { await decide.mutateAsync(approve); toast.success(approve ? `${r.category.name} budget saved` : "Recommendation dismissed"); } catch (e) { toast.error(errMsg(e)); }
  };
  const maxBar = Math.max(...b.months.map((m) => num(m.amount)), num(r.proposed_amount), 1);
  return (
    <div className="rounded-xl border border-line bg-bg/50 p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-serif text-xl">{r.category.name}</p>
          <Badge tone={r.confidence === "high" ? "success" : r.confidence === "medium" ? "gold" : "neutral"}>{r.confidence} confidence</Badge>
        </div>
        <div className="text-right">
          <p className="text-[10px] uppercase tracking-wider text-muted">Proposed</p>
          {editing ? <input className="input h-9 w-28 text-right" value={amount} onChange={(e) => setAmount(e.target.value)} aria-label="Adjust amount" />
            : <p className="font-serif text-2xl font-semibold tabular">{money(amount, cur, { decimals: false })}</p>}
        </div>
      </div>
      <div className="mt-4 flex h-14 items-end gap-1.5" aria-label="Historical monthly spend">
        {b.months.map((m) => (
          <div key={m.month} className="flex flex-1 flex-col items-center gap-1" title={`${fmtDate(m.month, "month")}: ${money(m.amount, cur)}`}>
            <div className="w-full rounded-t bg-gold/60" style={{ height: `${(num(m.amount) / maxBar) * 44 + 2}px` }} />
            <span className="text-[9px] text-muted">{new Date(m.month + "T00:00:00").toLocaleDateString("en-GB", { month: "narrow" })}</span>
          </div>
        ))}
        <div className="flex flex-1 flex-col items-center gap-1"><div className="w-full rounded-t border border-dashed border-forest bg-forest/20" style={{ height: `${(num(amount) / maxBar) * 44 + 2}px` }} /><span className="text-[9px] text-forest">new</span></div>
      </div>
      <p className="mt-3 text-[13px] leading-relaxed text-ink/90">{r.reason}</p>
      <p className="mt-2 text-[13px] text-muted"><span className="text-ink">Expected effect:</span> {r.expected_effect}</p>
      {r.limitations && <p className="mt-1 text-[12px] italic text-muted">{r.limitations}</p>}
      <div className="mt-4 flex flex-wrap gap-2">
        <Button size="sm" onClick={() => go(true)} loading={decide.isPending}><Check className="h-3.5 w-3.5" /> Approve</Button>
        <Button size="sm" variant="secondary" onClick={() => setEditing((e) => !e)}><Pencil className="h-3.5 w-3.5" /> Adjust</Button>
        <Button size="sm" variant="ghost" onClick={() => go(false)}><X className="h-3.5 w-3.5" /> Dismiss</Button>
      </div>
    </div>
  );
}

export default function Budgets() {
  const { user } = useAuth();
  const cur = user?.currency || "INR";
  const toast = useToast();
  const [month, setMonth] = useState(monthKey());
  const [modal, setModal] = useState<{ open: boolean; budget: BudgetRow | null }>({ open: false, budget: null });
  const [deleting, setDeleting] = useState<BudgetRow | null>(null);
  const { data, isLoading, error, refetch } = useBudgets(month);
  const recMonth = month === monthKey() ? shiftMonth(month, 1) : month;
  const recs = useRecommendations(recMonth);
  const del = useFinanceMutation((id: string) => api(`/budgets/${id}`, { method: "DELETE" }));
  const copy = useFinanceMutation(() => api<{ created: number }>("/budgets/copy-previous", { method: "POST", params: { month } }));
  const generate = useFinanceMutation(() => api<Recommendation[]>("/budgets/recommendations/generate", { body: { month: recMonth } }));
  const prevMap = new Map((data?.previous_month || []).map((b) => [b.category.id, b]));

  return (
    <>
      <PageHeader eyebrow="Smart budget planner" title="Budgets" subtitle="Set intentions per category, watch utilisation, and review recommendations grounded in your history."
        actions={<><MonthSwitcher month={month} onChange={setMonth} />
          <Button variant="secondary" onClick={async () => { const r = await copy.mutateAsync(); toast.info(r.created ? `Copied ${r.created} budgets from last month` : "Nothing new to copy"); }} loading={copy.isPending}><Copy className="h-4 w-4" /> Copy last month</Button>
          <Button onClick={() => setModal({ open: true, budget: null })}><Plus className="h-4 w-4" /> New budget</Button></>} />

      {error ? <ErrorState error={error} onRetry={refetch} /> : isLoading || !data ? <div className="grid gap-4 md:grid-cols-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-36" />)}</div> : (
        <>
          <div className="mb-6 grid gap-4 sm:grid-cols-4">
            {[["Budgeted", money(data.totals.budgeted, cur, { decimals: false })], ["Spent", money(data.totals.spent, cur, { decimals: false })],
              ["Remaining", money(data.totals.remaining, cur, { decimals: false })], ["Utilisation", `${data.totals.utilization}%`]].map(([k, v]) => (
              <div key={k} className="card p-5"><p className="text-[11px] uppercase tracking-[0.18em] text-muted">{k}</p><p className="mt-2 font-serif text-3xl font-semibold tabular">{v}</p></div>
            ))}
          </div>
          {!data.items.length ? (
            <EmptyState icon={<Wallet className="h-8 w-8" />} title={`No budgets for ${fmtDate(month, "month")}`} text="Create one per category, copy last month's, or approve a recommendation below."
              action={<Button onClick={() => setModal({ open: true, budget: null })}><Plus className="h-4 w-4" /> New budget</Button>} />
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {data.items.map((b) => {
                const prev = prevMap.get(b.category.id);
                return (
                  <div key={b.id} className="card group p-5">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: b.category.color || "#8A8577" }} /><p className="font-serif text-xl">{b.category.name}</p></div>
                      <Badge tone={STATUS[b.status][1]}>{STATUS[b.status][0]}</Badge>
                    </div>
                    <p className="mt-4 font-serif text-3xl font-semibold tabular">{money(b.spent, cur, { decimals: false })}<span className="text-base font-normal text-muted"> / {money(b.amount, cur, { decimals: false })}</span></p>
                    <div className="mt-3"><ProgressBar value={num(b.utilization)} tone={b.status === "exceeded" ? "danger" : b.status === "at_risk" ? "warning" : "forest"} label={`${b.category.name} utilisation`} /></div>
                    <div className="mt-2 flex justify-between text-xs text-muted">
                      <span>{b.utilization}% used</span>
                      <span className={num(b.remaining) < 0 ? "text-danger" : ""}>{num(b.remaining) < 0 ? `${money(-num(b.remaining), cur, { decimals: false })} over` : `${money(b.remaining, cur, { decimals: false })} left`}</span>
                    </div>
                    {prev && <p className="mt-2 text-[11px] text-muted">Last month: {money(prev.spent, cur, { decimals: false })} of {money(prev.amount, cur, { decimals: false })}</p>}
                    <div className="mt-4 flex gap-1 border-t border-line pt-3 opacity-80 transition group-hover:opacity-100">
                      <Button size="sm" variant="ghost" onClick={() => setModal({ open: true, budget: b })}><Pencil className="h-3.5 w-3.5" /> Edit</Button>
                      <Button size="sm" variant="ghost" className="text-danger" onClick={() => setDeleting(b)}><Trash2 className="h-3.5 w-3.5" /> Delete</Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      <Card className="mt-10" eyebrow={`Recommendations · ${fmtDate(recMonth, "month")}`} title={<span className="flex items-center gap-2"><Sparkles className="h-5 w-5 text-gold" /> Proposed budgets</span>}
        action={<Button variant="secondary" onClick={async () => { try { const r = await generate.mutateAsync(); toast.info(r.length ? `${r.length} recommendations prepared` : "Not enough history yet"); } catch (e) { toast.error(errMsg(e)); } }} loading={generate.isPending}>Analyse history</Button>}>
        <p className="mb-5 max-w-3xl text-sm text-muted">Calculated deterministically from up to six months of your spending (weighted recent average plus a dampened linear trend). Nothing is saved until you approve it.</p>
        {recs.isLoading ? <Skeleton className="h-40" /> : !recs.data?.length ? <p className="text-sm text-muted">No pending recommendations. Select “Analyse history” to compute them.</p> : (
          <div className="grid gap-4 lg:grid-cols-2">{recs.data.map((r) => <RecommendationCard key={r.id} r={r} cur={cur} />)}</div>
        )}
      </Card>

      <BudgetModal open={modal.open} budget={modal.budget} month={month} existing={(data?.items || []).map((b) => b.category.id)} onClose={() => setModal({ open: false, budget: null })} />
      <ConfirmDialog open={!!deleting} title="Delete budget" onClose={() => setDeleting(null)} loading={del.isPending}
        message={deleting && <>Remove the <strong>{deleting.category.name}</strong> budget for {fmtDate(deleting.month, "month")}?</>}
        onConfirm={async () => { try { await del.mutateAsync(deleting!.id); toast.success("Budget deleted"); setDeleting(null); } catch (e) { toast.error(errMsg(e)); } }} />
    </>
  );
}
