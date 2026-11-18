import { motion } from "framer-motion";
import { ArrowDownRight, ArrowUpRight, ChevronLeft, ChevronRight, Feather, Landmark, PiggyBank, Plus, ReceiptText, TrendingUp, Wallet } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { CategoryDonut, CategoryLegend, DailyTrend, IncomeExpenseChart } from "../components/charts";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, ProgressBar, Select, Skeleton } from "../components/ui";
import { useAuth } from "../lib/auth";
import { fmtDate, money, monthKey, num, shiftMonth } from "../lib/format";
import { useOverview } from "../lib/queries";
import { TransactionModal } from "./Transactions";

export function MonthSwitcher({ month, onChange }: { month: string; onChange: (m: string) => void }) {
  const isCurrent = month === monthKey();
  return (
    <div className="flex items-center gap-1 rounded-md border border-line bg-card p-1">
      <button className="rounded p-1.5 hover:bg-bg2" onClick={() => onChange(shiftMonth(month, -1))} aria-label="Previous month"><ChevronLeft className="h-4 w-4" /></button>
      <span className="min-w-[128px] text-center font-serif text-[15px]">{fmtDate(month, "month")}</span>
      <button className="rounded p-1.5 hover:bg-bg2 disabled:opacity-30" disabled={isCurrent} onClick={() => onChange(shiftMonth(month, 1))} aria-label="Next month"><ChevronRight className="h-4 w-4" /></button>
    </div>
  );
}

function Stat({ label, value, sub, icon, tone, delay }: { label: string; value: string; sub?: React.ReactNode; icon: React.ReactNode; tone?: "gold" | "forest"; delay: number }) {
  return (
    <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay, duration: 0.5 }}
      className={`card relative overflow-hidden p-5 ${tone === "forest" ? "border-forest bg-forest text-onforest dark:border-line dark:bg-[#22342a]" : ""}`}>
      <div className="flex items-start justify-between">
        <p className={`text-[11px] font-medium uppercase tracking-[0.18em] ${tone === "forest" ? "text-[#C2A56E]" : "text-muted"}`}>{label}</p>
        <span className={tone === "forest" ? "text-[#C2A56E]" : "text-gold"}>{icon}</span>
      </div>
      <p className="mt-3 font-serif text-[2rem] font-semibold leading-none tabular">{value}</p>
      {sub && <div className={`mt-2 text-xs ${tone === "forest" ? "text-onforest/70" : "text-muted"}`}>{sub}</div>}
    </motion.div>
  );
}

export default function Overview() {
  const { user } = useAuth();
  const cur = user?.currency || "INR";
  const [month, setMonth] = useState(monthKey());
  const [range, setRange] = useState(6);
  const [adding, setAdding] = useState(false);
  const { data, isLoading, error, refetch } = useOverview(month, range);

  const header = (
    <PageHeader eyebrow={new Date().toLocaleDateString("en-GB", { weekday: "long" })} title={`${greet()}, ${user?.full_name.split(" ")[0] ?? ""}.`}
      subtitle="A composed view of your finances, calculated from your recorded transactions."
      actions={<><MonthSwitcher month={month} onChange={setMonth} /><Button onClick={() => setAdding(true)}><Plus className="h-4 w-4" /> Add transaction</Button></>} />
  );

  if (error) return <>{header}<ErrorState error={error} onRetry={refetch} /></>;
  if (isLoading || !data) return (
    <>{header}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-32" />)}</div>
      <div className="mt-6 grid gap-6 lg:grid-cols-3"><Skeleton className="h-80 lg:col-span-2" /><Skeleton className="h-80" /></div>
    </>
  );

  const s = data.summary;
  const empty = s.transaction_count === 0 && data.recent_transactions.length === 0;
  const prev = data.monthly_series[data.monthly_series.length - 2];
  const expChange = prev && num(prev.expenses) > 0 ? ((num(s.expenses) - num(prev.expenses)) / num(prev.expenses)) * 100 : null;

  return (
    <>
      {header}
      <TransactionModal open={adding} onClose={() => setAdding(false)} />
      {empty ? (
        <EmptyState icon={<ReceiptText className="h-8 w-8" />} title="Your ledger awaits its first entry" text="Add a transaction, import a bank statement, or ask JOCASTA to record one for you."
          action={<div className="flex gap-2"><Button onClick={() => setAdding(true)}><Plus className="h-4 w-4" /> Add transaction</Button><Link to="/app/transactions?import=1"><Button variant="secondary">Import statement</Button></Link></div>} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <Stat label="Total balance" value={money(data.total_balance, cur, { decimals: false })} sub="All recorded income − expenses" icon={<Landmark className="h-4 w-4" />} tone="forest" delay={0} />
            <Stat label="Income" value={money(s.income, cur, { decimals: false })} sub={fmtDate(month, "month")} icon={<ArrowDownRight className="h-4 w-4" />} delay={0.05} />
            <Stat label="Expenses" value={money(s.expenses, cur, { decimals: false })} icon={<ArrowUpRight className="h-4 w-4" />} delay={0.1}
              sub={expChange === null ? `Avg ${money(data.average_monthly_expense, cur, { decimals: false })}/mo` : <span className={expChange > 0 ? "text-danger" : "text-success"}>{expChange > 0 ? "▲" : "▼"} {Math.abs(expChange).toFixed(1)}% vs last month</span>} />
            <Stat label="Savings" value={money(s.savings, cur, { decimals: false })} sub="Income − expenses this month" icon={<PiggyBank className="h-4 w-4" />} delay={0.15} />
            <Stat label="Savings rate" value={`${s.savings_rate}%`} sub={num(s.savings_rate) >= 20 ? "Healthy" : num(s.income) === 0 ? "No income recorded" : "Below 20% guideline"} icon={<TrendingUp className="h-4 w-4" />} delay={0.2} />
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2" eyebrow="Income vs expenditure" title="The past months"
              action={<Select aria-label="History range" value={range} onChange={(e) => setRange(Number(e.target.value))} className="w-32">{[3, 6, 12].map((n) => <option key={n} value={n}>{n} months</option>)}</Select>}>
              <IncomeExpenseChart data={data.monthly_series} currency={cur} />
            </Card>
            <Card eyebrow="Where it went" title="Categories">
              {data.category_breakdown.length ? <><CategoryDonut data={data.category_breakdown} currency={cur} height={200} /><div className="mt-4"><CategoryLegend data={data.category_breakdown} currency={cur} /></div></>
                : <p className="py-10 text-center text-sm text-muted">No expenses this month.</p>}
            </Card>
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2" eyebrow="Daily rhythm" title="Spending trend"><DailyTrend data={data.daily_trend} currency={cur} cumulative /></Card>
            <Card eyebrow="From JOCASTA" title={<span className="flex items-center gap-2"><Feather className="h-4 w-4 text-gold" /> Insights</span>}>
              <ul className="space-y-3">
                {data.insights.map((i, idx) => (
                  <li key={idx} className="flex gap-3 text-sm leading-relaxed">
                    <span className={`mt-2 h-1.5 w-1.5 shrink-0 rounded-full ${i.tone === "positive" ? "bg-success" : i.tone === "warning" ? "bg-danger" : "bg-gold"}`} />
                    <span className="text-ink/90">{i.text}</span>
                  </li>
                ))}
              </ul>
              <Link to="/app/jocasta" className="mt-5 inline-block text-sm text-gold hover:underline">Ask JOCASTA for a deeper analysis →</Link>
            </Card>
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-3">
            <Card eyebrow="This month" title="Budget progress" action={<Link to="/app/budgets" className="text-xs text-gold hover:underline">Manage</Link>}>
              {data.budgets.length ? (
                <ul className="space-y-4">
                  {data.budgets.slice(0, 6).map((b) => (
                    <li key={b.id}>
                      <div className="mb-1.5 flex items-center justify-between text-sm"><span>{b.category.name}</span>
                        <span className="tabular text-xs text-muted">{money(b.spent, cur, { decimals: false })} / {money(b.amount, cur, { decimals: false })}</span></div>
                      <ProgressBar value={num(b.utilization)} tone={b.status === "exceeded" ? "danger" : b.status === "at_risk" ? "warning" : "forest"} label={`${b.category.name} budget`} />
                    </li>
                  ))}
                </ul>
              ) : <EmptyState icon={<Wallet className="h-6 w-6" />} title="No budgets yet" action={<Link to="/app/budgets"><Button size="sm" variant="secondary">Create a budget</Button></Link>} />}
            </Card>
            <Card eyebrow="Ambitions" title="Savings goals" action={<Link to="/app/savings" className="text-xs text-gold hover:underline">View all</Link>}>
              {data.goals.length ? (
                <ul className="space-y-4">
                  {data.goals.slice(0, 4).map((g) => (
                    <li key={g.id}>
                      <div className="mb-1.5 flex items-center justify-between text-sm"><span>{g.name}</span><span className="tabular text-xs text-muted">{g.progress_percent}%</span></div>
                      <ProgressBar value={num(g.progress_percent)} tone="gold" label={`${g.name} progress`} />
                      <p className="mt-1 text-[11px] text-muted">{money(g.remaining_amount, cur, { decimals: false })} to go{g.required_monthly ? ` · ${money(g.required_monthly, cur, { decimals: false })}/month` : ""}</p>
                    </li>
                  ))}
                </ul>
              ) : <EmptyState icon={<PiggyBank className="h-6 w-6" />} title="No goals yet" action={<Link to="/app/savings"><Button size="sm" variant="secondary">Set a goal</Button></Link>} />}
            </Card>
            <Card eyebrow="Latest entries" title="Recent transactions" action={<Link to="/app/transactions" className="text-xs text-gold hover:underline">All</Link>}>
              <ul className="divide-y divide-line">
                {data.recent_transactions.map((t) => (
                  <li key={t.id} className="flex items-center justify-between gap-3 py-2.5">
                    <div className="min-w-0"><p className="truncate text-sm">{t.description}</p><p className="text-[11px] text-muted">{t.category} · {fmtDate(t.date)}</p></div>
                    <span className={`shrink-0 text-sm tabular ${t.type === "income" ? "text-success" : "text-ink"}`}>{t.type === "income" ? "+" : "−"}{money(t.amount, cur)}</span>
                  </li>
                ))}
              </ul>
              {data.recent_transactions.some((t) => t.confidence && num(t.confidence) < 0.5) && <Badge tone="warning" className="mt-3">Some entries need category review</Badge>}
            </Card>
          </div>
        </>
      )}
    </>
  );
}

function greet() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}
