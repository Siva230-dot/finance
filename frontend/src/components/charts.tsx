import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { money, num } from "../lib/format";
import type { CategorySlice } from "../types";

export const CHART = { income: "rgb(var(--olive))", expense: "rgb(var(--gold))", savings: "rgb(var(--forest))", grid: "rgb(var(--line))" };
const FALLBACK = ["#A58B58", "#25382D", "#5A6751", "#574637", "#8C6E5A", "#7D6B91", "#4F6D7A", "#B4846C", "#6B7F5E", "#3F5E5A"];

function TooltipBox({ active, payload, label, currency, labelFmt }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string; currency: string; labelFmt?: (l: string) => string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-line bg-card px-3 py-2 text-xs shadow-lift">
      {label && <p className="mb-1 font-serif text-sm text-ink">{labelFmt ? labelFmt(label) : label}</p>}
      {payload.map((p) => (
        <p key={p.name} className="flex items-center justify-between gap-4 tabular">
          <span className="flex items-center gap-1.5 text-muted"><span className="h-2 w-2 rounded-full" style={{ background: p.color }} />{p.name}</span>
          <span className="text-ink">{money(p.value, currency)}</span>
        </p>
      ))}
    </div>
  );
}

const monthLabel = (m: string) => new Date(m + "T00:00:00").toLocaleDateString("en-GB", { month: "short" });
const monthLong = (m: string) => new Date(m + "T00:00:00").toLocaleDateString("en-GB", { month: "long", year: "numeric" });

export function IncomeExpenseChart({ data, currency, height = 280 }: { data: { month: string; income: string; expenses: string; savings: string }[]; currency: string; height?: number }) {
  const rows = data.map((d) => ({ month: d.month, Income: num(d.income), Expenses: num(d.expenses), Savings: num(d.savings) }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={rows} barGap={4} margin={{ top: 8, right: 4, left: 4, bottom: 0 }}>
        <CartesianGrid vertical={false} strokeDasharray="2 4" />
        <XAxis dataKey="month" tickFormatter={monthLabel} axisLine={false} tickLine={false} />
        <YAxis tickFormatter={(v) => money(v, currency, { compact: true })} axisLine={false} tickLine={false} width={56} />
        <Tooltip content={<TooltipBox currency={currency} labelFmt={monthLong} />} />
        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="Income" fill={CHART.income} radius={[3, 3, 0, 0]} maxBarSize={28} animationDuration={900} />
        <Bar dataKey="Expenses" fill={CHART.expense} radius={[3, 3, 0, 0]} maxBarSize={28} animationDuration={900} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function SavingsLine({ data, currency, height = 240 }: { data: { month: string; savings: string }[]; currency: string; height?: number }) {
  const rows = data.map((d) => ({ month: d.month, Savings: num(d.savings) }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={rows} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
        <CartesianGrid vertical={false} strokeDasharray="2 4" />
        <XAxis dataKey="month" tickFormatter={monthLabel} axisLine={false} tickLine={false} />
        <YAxis tickFormatter={(v) => money(v, currency, { compact: true })} axisLine={false} tickLine={false} width={56} />
        <Tooltip content={<TooltipBox currency={currency} labelFmt={monthLong} />} />
        <Line type="monotone" dataKey="Savings" stroke={CHART.savings} strokeWidth={2.2} dot={{ r: 3, fill: CHART.expense }} animationDuration={1100} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function DailyTrend({ data, currency, height = 220, cumulative = false }: { data: { date: string; amount: string; cumulative: string }[]; currency: string; height?: number; cumulative?: boolean }) {
  const rows = data.map((d) => ({ date: d.date, Spent: num(cumulative ? d.cumulative : d.amount) }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={rows} margin={{ top: 8, right: 4, left: 4, bottom: 0 }}>
        <defs>
          <linearGradient id="spendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(var(--gold))" stopOpacity={0.35} />
            <stop offset="100%" stopColor="rgb(var(--gold))" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} strokeDasharray="2 4" />
        <XAxis dataKey="date" tickFormatter={(d) => String(Number(d.slice(8)))} axisLine={false} tickLine={false} interval="preserveStartEnd" minTickGap={14} />
        <YAxis tickFormatter={(v) => money(v, currency, { compact: true })} axisLine={false} tickLine={false} width={56} />
        <Tooltip content={<TooltipBox currency={currency} labelFmt={(l) => new Date(l + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "long" })} />} />
        <Area type="monotone" dataKey="Spent" name={cumulative ? "Cumulative spend" : "Spent"} stroke="rgb(var(--gold))" strokeWidth={2} fill="url(#spendFill)" animationDuration={1000} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function CategoryDonut({ data, currency, height = 240 }: { data: CategorySlice[]; currency: string; height?: number }) {
  const rows = data.map((d, i) => ({ name: d.category, value: num(d.amount), color: d.color || FALLBACK[i % FALLBACK.length] }));
  const total = rows.reduce((s, r) => s + r.value, 0);
  return (
    <div className="relative" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={rows} dataKey="value" nameKey="name" innerRadius="64%" outerRadius="92%" paddingAngle={1.5} stroke="rgb(var(--card))" strokeWidth={2} animationDuration={900}>
            {rows.map((r) => <Cell key={r.name} fill={r.color} />)}
          </Pie>
          <Tooltip content={<TooltipBox currency={currency} />} />
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <p className="text-[10px] uppercase tracking-[0.2em] text-muted">Spent</p>
        <p className="font-serif text-2xl font-semibold tabular text-ink">{money(total, currency, { compact: true })}</p>
      </div>
    </div>
  );
}

export function CategoryLegend({ data, currency }: { data: CategorySlice[]; currency: string }) {
  return (
    <ul className="space-y-2">
      {data.slice(0, 7).map((c, i) => (
        <li key={c.category_id} className="flex items-center justify-between gap-3 text-sm">
          <span className="flex min-w-0 items-center gap-2"><span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: c.color || FALLBACK[i % FALLBACK.length] }} /><span className="truncate text-ink">{c.category}</span></span>
          <span className="shrink-0 tabular text-muted">{money(c.amount, currency, { decimals: false })} <span className="ml-1 text-[11px]">{c.share}%</span></span>
        </li>
      ))}
    </ul>
  );
}
