import { motion } from "framer-motion";
import { CalendarClock, HandCoins, Pencil, PiggyBank, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge, Button, ConfirmDialog, EmptyState, ErrorState, Input, Modal, PageHeader, Select, Skeleton, Textarea, errMsg, useToast } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate, money, num, todayISO } from "../lib/format";
import { useFinanceMutation, useGoals } from "../lib/queries";
import type { Goal } from "../types";

const AMOUNT = /^-?\d{1,12}(\.\d{1,2})?$/;

function Ring({ pct }: { pct: number }) {
  const r = 46, c = 2 * Math.PI * r, p = Math.min(100, Math.max(0, pct));
  return (
    <svg viewBox="0 0 110 110" className="h-28 w-28 -rotate-90" aria-hidden>
      <circle cx="55" cy="55" r={r} fill="none" stroke="rgb(var(--bg2))" strokeWidth="8" />
      <motion.circle cx="55" cy="55" r={r} fill="none" stroke="rgb(var(--gold))" strokeWidth="8" strokeLinecap="round" strokeDasharray={c}
        initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c - (p / 100) * c }} transition={{ duration: 1.2, ease: [0.22, 1, 0.36, 1] }} />
    </svg>
  );
}

function GoalModal({ open, onClose, goal }: { open: boolean; onClose: () => void; goal: Goal | null }) {
  const toast = useToast();
  const [v, setV] = useState({ name: "", target_amount: "", current_amount: "", target_date: "", notes: "", status: "active" });
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (open) { setErr(null); setV(goal ? { name: goal.name, target_amount: goal.target_amount, current_amount: "", target_date: goal.target_date || "", notes: goal.notes || "", status: goal.status } : { name: "", target_amount: "", current_amount: "", target_date: "", notes: "", status: "active" }); }
  }, [open, goal]);
  const save = useFinanceMutation(() => goal
    ? api(`/savings/${goal.id}`, { method: "PATCH", body: { name: v.name, target_amount: v.target_amount, target_date: v.target_date || null, notes: v.notes || null, status: v.status } })
    : api("/savings", { body: { name: v.name, target_amount: v.target_amount, current_amount: v.current_amount || "0", target_date: v.target_date || null, notes: v.notes || null } }));
  const submit = async () => {
    if (!v.name.trim()) return setErr("Give the goal a name");
    if (!AMOUNT.test(v.target_amount) || Number(v.target_amount) <= 0) return setErr("Enter a positive target amount");
    if (v.current_amount && (!AMOUNT.test(v.current_amount) || Number(v.current_amount) < 0)) return setErr("Current savings must be zero or more");
    if (v.target_date && v.target_date <= todayISO() && !goal) return setErr("Target date must be in the future");
    try { await save.mutateAsync(); toast.success(goal ? "Goal updated" : "Goal created"); onClose(); } catch (e) { setErr(errMsg(e)); }
  };
  const set = (k: keyof typeof v) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setV({ ...v, [k]: e.target.value });
  return (
    <Modal open={open} onClose={onClose} title={goal ? "Edit savings goal" : "New savings goal"} footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button onClick={submit} loading={save.isPending}>Save goal</Button></>}>
      <div className="space-y-4">
        <Input label="Goal" placeholder="e.g. New laptop" value={v.name} onChange={set("name")} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Target amount" inputMode="decimal" value={v.target_amount} onChange={set("target_amount")} />
          {goal ? <Select label="Status" value={v.status} onChange={set("status")}><option value="active">Active</option><option value="completed">Completed</option><option value="archived">Archived</option></Select>
            : <Input label="Already saved" inputMode="decimal" placeholder="0" value={v.current_amount} onChange={set("current_amount")} />}
        </div>
        <Input label="Target date (optional)" type="date" value={v.target_date} min={todayISO()} onChange={set("target_date")} hint="Used to calculate the required monthly contribution." />
        <Textarea label="Notes" rows={2} value={v.notes} onChange={set("notes")} />
        {err && <p role="alert" className="text-sm text-danger">{err}</p>}
      </div>
    </Modal>
  );
}

function ContributionModal({ goal, onClose }: { goal: Goal | null; onClose: () => void }) {
  const toast = useToast();
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(todayISO());
  const [note, setNote] = useState("");
  const [withdraw, setWithdraw] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { setAmount(""); setNote(""); setErr(null); setWithdraw(false); setDate(todayISO()); }, [goal]);
  const save = useFinanceMutation(() => api(`/savings/${goal!.id}/contributions`, { body: { amount: withdraw ? `-${amount}` : amount, contribution_date: date, note: note || null } }));
  const submit = async () => {
    if (!/^\d{1,12}(\.\d{1,2})?$/.test(amount) || Number(amount) <= 0) return setErr("Enter a positive amount");
    try { await save.mutateAsync(); toast.success(withdraw ? "Withdrawal recorded" : "Contribution recorded"); onClose(); } catch (e) { setErr(errMsg(e)); }
  };
  return (
    <Modal open={!!goal} onClose={onClose} title={`Record savings · ${goal?.name ?? ""}`} footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button onClick={submit} loading={save.isPending}>Record</Button></>}>
      <div className="space-y-4">
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={withdraw} onChange={(e) => setWithdraw(e.target.checked)} /> This is a withdrawal</label>
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Amount" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
          <Input label="Date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>
        <Input label="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
        {err && <p role="alert" className="text-sm text-danger">{err}</p>}
      </div>
    </Modal>
  );
}

export default function Savings() {
  const { user } = useAuth();
  const cur = user?.currency || "INR";
  const toast = useToast();
  const { data, isLoading, error, refetch } = useGoals();
  const [modal, setModal] = useState<{ open: boolean; goal: Goal | null }>({ open: false, goal: null });
  const [contrib, setContrib] = useState<Goal | null>(null);
  const [deleting, setDeleting] = useState<Goal | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const del = useFinanceMutation((id: string) => api(`/savings/${id}`, { method: "DELETE" }));
  const active = (data || []).filter((g) => g.status === "active");
  const totalSaved = (data || []).reduce((s, g) => s + num(g.current_amount), 0);
  const totalTarget = active.reduce((s, g) => s + num(g.target_amount), 0);
  const monthlyNeed = active.reduce((s, g) => s + num(g.required_monthly), 0);

  return (
    <>
      <PageHeader eyebrow="Ambitions, made measurable" title="Savings Goals" subtitle="Each goal shows what remains and the monthly contribution needed to arrive on time."
        actions={<Button onClick={() => setModal({ open: true, goal: null })}><Plus className="h-4 w-4" /> New goal</Button>} />
      {error ? <ErrorState error={error} onRetry={refetch} /> : isLoading ? <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-72" />)}</div> : !data?.length ? (
        <EmptyState icon={<PiggyBank className="h-8 w-8" />} title="No savings goals yet" text="Name something worth saving for — a laptop, a journey, a safety net." action={<Button onClick={() => setModal({ open: true, goal: null })}><Plus className="h-4 w-4" /> Create a goal</Button>} />
      ) : (
        <>
          <div className="mb-6 grid gap-4 sm:grid-cols-3">
            {[["Total saved", money(totalSaved, cur, { decimals: false })], ["Active targets", money(totalTarget, cur, { decimals: false })], ["Needed per month", money(monthlyNeed, cur, { decimals: false })]].map(([k, v]) => (
              <div key={k} className="card p-5"><p className="text-[11px] uppercase tracking-[0.18em] text-muted">{k}</p><p className="mt-2 font-serif text-3xl font-semibold tabular">{v}</p></div>
            ))}
          </div>
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {data.map((g, i) => (
              <motion.div key={g.id} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }} className="card flex flex-col p-6">
                <div className="flex items-start justify-between gap-3">
                  <div><p className="font-serif text-2xl leading-tight">{g.name}</p>
                    {g.target_date && <p className="mt-1 flex items-center gap-1 text-xs text-muted"><CalendarClock className="h-3.5 w-3.5" /> by {fmtDate(g.target_date, "long")}</p>}</div>
                  <Badge tone={g.status === "completed" ? "success" : g.status === "archived" ? "neutral" : "gold"}>{g.status}</Badge>
                </div>
                <div className="my-5 flex items-center gap-5">
                  <div className="relative"><Ring pct={num(g.progress_percent)} /><span className="absolute inset-0 grid place-items-center font-serif text-xl font-semibold">{g.progress_percent}%</span></div>
                  <dl className="space-y-1.5 text-sm">
                    <div><dt className="text-[10px] uppercase tracking-wider text-muted">Saved</dt><dd className="tabular font-medium">{money(g.current_amount, cur)}</dd></div>
                    <div><dt className="text-[10px] uppercase tracking-wider text-muted">Target</dt><dd className="tabular">{money(g.target_amount, cur)}</dd></div>
                    <div><dt className="text-[10px] uppercase tracking-wider text-muted">Remaining</dt><dd className="tabular">{money(g.remaining_amount, cur)}</dd></div>
                  </dl>
                </div>
                {g.required_monthly && g.status === "active" && (
                  <p className="rounded-md bg-bg2/70 px-3 py-2 text-[13px]">Save <strong className="tabular">{money(g.required_monthly, cur)}</strong> a month for {g.months_remaining} month{g.months_remaining === 1 ? "" : "s"} to reach it.</p>
                )}
                {g.target_date && g.months_remaining === 0 && num(g.remaining_amount) > 0 && <p className="mt-2 text-[13px] text-danger">The target date has passed with {money(g.remaining_amount, cur)} remaining.</p>}
                <button className="mt-4 text-left text-xs text-gold hover:underline" onClick={() => setExpanded(expanded === g.id ? null : g.id)} aria-expanded={expanded === g.id}>
                  {expanded === g.id ? "Hide" : "Show"} contribution history ({g.contributions.length})
                </button>
                {expanded === g.id && (
                  <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto text-[13px]">
                    {g.contributions.map((c) => <li key={c.id} className="flex justify-between"><span className="text-muted">{fmtDate(c.contribution_date)}{c.note ? ` · ${c.note}` : ""}</span><span className={`tabular ${num(c.amount) < 0 ? "text-danger" : "text-success"}`}>{num(c.amount) < 0 ? "−" : "+"}{money(Math.abs(num(c.amount)), cur)}</span></li>)}
                    {!g.contributions.length && <li className="text-muted">No contributions yet.</li>}
                  </ul>
                )}
                <div className="mt-auto flex gap-1 border-t border-line pt-3">
                  <Button size="sm" onClick={() => setContrib(g)}><HandCoins className="h-3.5 w-3.5" /> Add savings</Button>
                  <Button size="sm" variant="ghost" onClick={() => setModal({ open: true, goal: g })} aria-label={`Edit ${g.name}`}><Pencil className="h-3.5 w-3.5" /></Button>
                  <Button size="sm" variant="ghost" className="text-danger" onClick={() => setDeleting(g)} aria-label={`Delete ${g.name}`}><Trash2 className="h-3.5 w-3.5" /></Button>
                </div>
              </motion.div>
            ))}
          </div>
        </>
      )}
      <GoalModal open={modal.open} goal={modal.goal} onClose={() => setModal({ open: false, goal: null })} />
      <ContributionModal goal={contrib} onClose={() => setContrib(null)} />
      <ConfirmDialog open={!!deleting} title="Delete savings goal" onClose={() => setDeleting(null)} loading={del.isPending}
        message={deleting && <>Delete <strong>{deleting.name}</strong> and its progress ({money(deleting.current_amount, cur)} recorded)?</>}
        onConfirm={async () => { try { await del.mutateAsync(deleting!.id); toast.success("Goal deleted"); setDeleting(null); } catch (e) { toast.error(errMsg(e)); } }} />
    </>
  );
}
