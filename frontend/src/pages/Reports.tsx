import { useQuery } from "@tanstack/react-query";
import { FileDown, FileSpreadsheet } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, ErrorState, PageHeader, Select, Skeleton, errMsg, useToast } from "../components/ui";
import { api, download } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate, money, monthKey, num } from "../lib/format";
import type { BudgetRow, CategorySlice, Summary } from "../types";
import { MonthSwitcher } from "./Overview";

type Report = { title: string; summary: Summary; category_breakdown: CategorySlice[]; income_breakdown: CategorySlice[]; budgets?: BudgetRow[]; months?: { month: string; income: string; expenses: string; savings: string; savings_rate: string }[];
  goals: { id: string; name: string; target_amount: string; current_amount: string; progress_percent: string }[]; period_start: string; period_end: string };

export default function Reports() {
  const { user } = useAuth();
  const cur = user?.currency || "INR";
  const toast = useToast();
  const [type, setType] = useState<"monthly" | "annual">("monthly");
  const [month, setMonth] = useState(monthKey());
  const [year, setYear] = useState(new Date().getFullYear());
  const [busy, setBusy] = useState<string | null>(null);
  const params = type === "monthly" ? { month } : { year };
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["report", type, month, year], queryFn: () => api<Report>(`/reports/${type}`, { params }) });
  const dl = async (format: "pdf" | "csv") => {
    setBusy(format);
    try { await download(`/reports/${type}/download`, { ...params, format }, `financemate-report.${format}`); toast.success(`${format.toUpperCase()} downloaded`); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(null); }
  };
  const history = useQuery({ queryKey: ["report", "history", busy], queryFn: () => api<{ id: string; report_type: string; period_start: string; created_at: string }[]>("/reports") });

  return (
    <>
      <PageHeader eyebrow="Statements" title="Financial Reports" subtitle="Monthly and annual reports built from your records — download as PDF or CSV."
        actions={<>
          <Select aria-label="Report type" value={type} onChange={(e) => setType(e.target.value as "monthly" | "annual")} className="w-36"><option value="monthly">Monthly</option><option value="annual">Annual</option></Select>
          {type === "monthly" ? <MonthSwitcher month={month} onChange={setMonth} /> : <Select aria-label="Year" value={year} onChange={(e) => setYear(+e.target.value)} className="w-28">{Array.from({ length: 6 }, (_, i) => new Date().getFullYear() - i).map((y) => <option key={y}>{y}</option>)}</Select>}
          <Button variant="secondary" onClick={() => dl("csv")} loading={busy === "csv"}><FileSpreadsheet className="h-4 w-4" /> CSV</Button>
          <Button onClick={() => dl("pdf")} loading={busy === "pdf"}><FileDown className="h-4 w-4" /> PDF</Button>
        </>} />
      {error ? <ErrorState error={error} onRetry={refetch} /> : isLoading || !data ? <Skeleton className="h-[480px]" /> : (
        <div className="card paper-texture mx-auto max-w-4xl overflow-hidden">
          <div className="border-b-2 border-double border-gold/50 px-8 py-8 sm:px-12">
            <p className="eyebrow">AI FinanceMate</p>
            <h2 className="mt-2 font-serif text-4xl font-semibold">{data.title}</h2>
            <p className="mt-1 text-sm text-muted">Prepared for {user?.full_name} · {fmtDate(data.period_start, "long")} – {fmtDate(data.period_end, "long")}</p>
          </div>
          <div className="space-y-10 px-8 py-8 sm:px-12">
            <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
              {[["Income", money(data.summary.income, cur)], ["Expenses", money(data.summary.expenses, cur)], ["Net savings", money(data.summary.savings, cur)], ["Savings rate", `${data.summary.savings_rate}%`]].map(([k, v]) => (
                <div key={k}><p className="text-[10px] uppercase tracking-[0.2em] text-muted">{k}</p><p className="mt-1 font-serif text-2xl font-semibold tabular">{v}</p></div>
              ))}
            </div>
            {data.months && (
              <section><h3 className="mb-3 font-serif text-2xl">Month by month</h3>
                <table className="w-full text-sm"><thead className="border-b border-gold/50 text-left text-[11px] uppercase tracking-wider text-muted"><tr><th className="py-2">Month</th><th className="py-2 text-right">Income</th><th className="py-2 text-right">Expenses</th><th className="py-2 text-right">Savings</th></tr></thead>
                  <tbody className="divide-y divide-line">{data.months.map((m) => <tr key={m.month}><td className="py-1.5">{fmtDate(m.month, "month")}</td><td className="py-1.5 text-right tabular">{money(m.income, cur, { decimals: false })}</td><td className="py-1.5 text-right tabular">{money(m.expenses, cur, { decimals: false })}</td><td className={`py-1.5 text-right tabular ${num(m.savings) < 0 ? "text-danger" : ""}`}>{money(m.savings, cur, { decimals: false })}</td></tr>)}</tbody></table>
              </section>
            )}
            <section><h3 className="mb-3 font-serif text-2xl">Expense breakdown</h3>
              {data.category_breakdown.length ? (
                <ul className="space-y-2.5">{data.category_breakdown.map((c) => (
                  <li key={c.category_id} className="grid grid-cols-[1fr,auto] items-center gap-x-4 text-sm">
                    <span>{c.category} <span className="text-xs text-muted">· {c.count} entries</span></span><span className="tabular">{money(c.amount, cur)} <span className="text-xs text-muted">{c.share}%</span></span>
                    <div className="col-span-2 mt-1 h-1 rounded-full bg-bg2"><div className="h-full rounded-full bg-gold/70" style={{ width: `${num(c.share)}%` }} /></div>
                  </li>))}</ul>
              ) : <p className="text-sm text-muted">No expenses recorded in this period.</p>}
            </section>
            {!!data.budgets?.length && (
              <section><h3 className="mb-3 font-serif text-2xl">Budget performance</h3>
                <table className="w-full text-sm"><thead className="border-b border-gold/50 text-left text-[11px] uppercase tracking-wider text-muted"><tr><th className="py-2">Category</th><th className="py-2 text-right">Budget</th><th className="py-2 text-right">Spent</th><th className="py-2 text-right">Status</th></tr></thead>
                  <tbody className="divide-y divide-line">{data.budgets.map((b) => <tr key={b.id}><td className="py-1.5">{b.category.name}</td><td className="py-1.5 text-right tabular">{money(b.amount, cur, { decimals: false })}</td><td className="py-1.5 text-right tabular">{money(b.spent, cur, { decimals: false })}</td><td className="py-1.5 text-right"><Badge tone={b.status === "exceeded" ? "danger" : b.status === "at_risk" ? "warning" : "success"}>{b.utilization}%</Badge></td></tr>)}</tbody></table>
              </section>
            )}
            {!!data.goals.length && (
              <section><h3 className="mb-3 font-serif text-2xl">Savings progress</h3>
                <ul className="grid gap-3 sm:grid-cols-2">{data.goals.map((g) => <li key={g.id} className="rounded-lg border border-line p-3 text-sm"><p className="font-serif text-lg">{g.name}</p><p className="tabular text-muted">{money(g.current_amount, cur, { decimals: false })} of {money(g.target_amount, cur, { decimals: false })} · {g.progress_percent}%</p></li>)}</ul>
              </section>
            )}
            <p className="border-t border-line pt-4 text-[11px] italic text-muted">Figures are calculated from transactions recorded in AI FinanceMate. Informational only; not financial advice.</p>
          </div>
        </div>
      )}
      {!!history.data?.length && (
        <Card className="mx-auto mt-8 max-w-4xl" eyebrow="Archive" title="Recently generated">
          <ul className="divide-y divide-line text-sm">{history.data.slice(0, 8).map((h) => <li key={h.id} className="flex justify-between py-2"><span className="capitalize">{h.report_type} · {h.report_type === "annual" ? h.period_start.slice(0, 4) : fmtDate(h.period_start, "month")}</span><span className="text-muted">{fmtDate(h.created_at)}</span></li>)}</ul>
        </Card>
      )}
    </>
  );
}
