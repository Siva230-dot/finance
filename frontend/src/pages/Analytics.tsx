import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { CategoryDonut, CategoryLegend, DailyTrend, IncomeExpenseChart, SavingsLine } from "../components/charts";
import { Card, ErrorState, PageHeader, ProgressBar, Select, Skeleton, cx } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate, money, monthKey, num } from "../lib/format";
import { useBudgets } from "../lib/queries";
import type { CategorySlice } from "../types";
import { MonthSwitcher } from "./Overview";

type Trends = { monthly: { month: string; income: string; expenses: string; savings: string }[]; daily: { date: string; amount: string; cumulative: string }[]; average_monthly_expense: string };
type Delta = { current: string; previous: string; change: string; change_percent: string | null };
type Comparison = { current_month: string; previous_month: string; income: Delta; expenses: Delta; savings: Delta; category_changes: { category: string; current: string; previous: string; change: string; change_percent: string | null }[] };

export default function Analytics() {
  const { user } = useAuth();
  const cur = user?.currency || "INR";
  const [month, setMonth] = useState(monthKey());
  const [months, setMonths] = useState(12);
  const end = `${month.slice(0, 8)}${String(new Date(+month.slice(0, 4), +month.slice(5, 7), 0).getDate()).padStart(2, "0")}`; // local date, no UTC shift
  const trends = useQuery({ queryKey: ["analytics", "trends", month, months], queryFn: () => api<Trends>("/analytics/trends", { params: { month, months } }) });
  const comp = useQuery({ queryKey: ["analytics", "comparison", month], queryFn: () => api<Comparison>("/analytics/comparison", { params: { month } }) });
  const cats = useQuery({ queryKey: ["analytics", "cats", month], queryFn: () => api<CategorySlice[]>("/analytics/categories", { params: { start_date: month, end_date: end } }) });
  const budgets = useBudgets(month);
  const err = trends.error || comp.error || cats.error;

  return (
    <>
      <PageHeader eyebrow="Financial analytics" title="Patterns & movements" subtitle="Every chart is computed from your stored transactions using exact decimal arithmetic."
        actions={<><MonthSwitcher month={month} onChange={setMonth} /><Select aria-label="Range" value={months} onChange={(e) => setMonths(+e.target.value)} className="w-36">{[6, 12, 24].map((n) => <option key={n} value={n}>{n} months</option>)}</Select></>} />
      {err ? <ErrorState error={err} onRetry={() => { trends.refetch(); comp.refetch(); cats.refetch(); }} /> : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {comp.data ? ([["Income", comp.data.income, false], ["Expenditure", comp.data.expenses, true], ["Savings", comp.data.savings, false]] as const).map(([k, d, inverse]) => {
              const up = num(d.change) > 0, good = inverse ? !up : up;
              return (
                <div key={k} className="card p-5">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-muted">{k} · {fmtDate(month, "month")}</p>
                  <p className="mt-2 font-serif text-3xl font-semibold tabular">{money(d.current, cur, { decimals: false })}</p>
                  <p className={cx("mt-1 text-xs", num(d.change) === 0 ? "text-muted" : good ? "text-success" : "text-danger")}>
                    {num(d.change) === 0 ? "No change" : `${up ? "▲" : "▼"} ${money(Math.abs(num(d.change)), cur, { decimals: false })}${d.change_percent ? ` (${Math.abs(num(d.change_percent))}%)` : ""}`} vs previous month
                  </p>
                </div>
              );
            }) : Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
            <div className="card p-5"><p className="text-[11px] uppercase tracking-[0.18em] text-muted">Avg monthly spend</p>
              <p className="mt-2 font-serif text-3xl font-semibold tabular">{trends.data ? money(trends.data.average_monthly_expense, cur, { decimals: false }) : "—"}</p><p className="mt-1 text-xs text-muted">Months with recorded data</p></div>
          </div>
          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2" eyebrow="Income versus expenditure" title={`Last ${months} months`}>{trends.data ? <IncomeExpenseChart data={trends.data.monthly} currency={cur} height={300} /> : <Skeleton className="h-72" />}</Card>
            <Card eyebrow="Category-wise" title="Expenditure">{cats.data ? (cats.data.length ? <><CategoryDonut data={cats.data} currency={cur} height={190} /><div className="mt-4"><CategoryLegend data={cats.data} currency={cur} /></div></> : <p className="py-12 text-center text-sm text-muted">No expenses recorded.</p>) : <Skeleton className="h-72" />}</Card>
          </div>
          <div className="grid gap-6 lg:grid-cols-2">
            <Card eyebrow="Daily expense trend" title={fmtDate(month, "month")}>{trends.data ? <DailyTrend data={trends.data.daily} currency={cur} /> : <Skeleton className="h-56" />}</Card>
            <Card eyebrow="Net savings" title="Monthly savings">{trends.data ? <SavingsLine data={trends.data.monthly} currency={cur} height={220} /> : <Skeleton className="h-56" />}</Card>
          </div>
          <div className="grid gap-6 lg:grid-cols-2">
            <Card eyebrow="Month over month" title="What changed">
              {comp.data?.category_changes.length ? (
                <table className="w-full text-sm">
                  <thead className="text-left text-[11px] uppercase tracking-wider text-muted"><tr><th className="pb-2">Category</th><th className="pb-2 text-right">Previous</th><th className="pb-2 text-right">Current</th><th className="pb-2 text-right">Change</th></tr></thead>
                  <tbody className="divide-y divide-line">
                    {comp.data.category_changes.slice(0, 10).map((c) => (
                      <tr key={c.category}><td className="py-2">{c.category}</td><td className="py-2 text-right tabular text-muted">{money(c.previous, cur, { decimals: false })}</td><td className="py-2 text-right tabular">{money(c.current, cur, { decimals: false })}</td>
                        <td className={cx("py-2 text-right tabular", num(c.change) > 0 ? "text-danger" : num(c.change) < 0 ? "text-success" : "text-muted")}>{num(c.change) > 0 ? "+" : num(c.change) < 0 ? "−" : ""}{money(Math.abs(num(c.change)), cur, { decimals: false })}</td></tr>
                    ))}
                  </tbody>
                </table>
              ) : <p className="text-sm text-muted">Not enough data to compare.</p>}
            </Card>
            <Card eyebrow="Budget utilisation" title={fmtDate(month, "month")}>
              {budgets.data?.items.length ? (
                <ul className="space-y-4">{budgets.data.items.map((b) => (
                  <li key={b.id}><div className="mb-1.5 flex justify-between text-sm"><span>{b.category.name}</span><span className="tabular text-xs text-muted">{b.utilization}%</span></div>
                    <ProgressBar value={num(b.utilization)} tone={b.status === "exceeded" ? "danger" : b.status === "at_risk" ? "warning" : "forest"} /></li>
                ))}</ul>
              ) : <p className="text-sm text-muted">No budgets set for this month.</p>}
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
