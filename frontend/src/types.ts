export type Money = string; // decimal string from the API — never float math on money

export interface User { id: string; email: string; full_name: string; currency: string; theme_preference: "light" | "dark" | "system"; created_at: string }
export interface Category { id: string; name: string; slug: string; kind: "income" | "expense" | "both"; color: string | null; icon: string | null; is_system: boolean }
export interface Transaction {
  id: string; description: string; amount: Money; type: "income" | "expense"; category: Category; transaction_date: string;
  payment_method: string | null; notes: string | null; is_recurring: boolean; recurrence_interval: string | null;
  categorization_source: string; categorization_confidence: string | null; created_at: string; updated_at: string;
}
export interface TxRow { id: string; description: string; amount: Money; type: string; category: string; date: string; payment_method?: string | null; confidence?: string | null; categorization_source?: string }
export interface Page<T> { items: T[]; total: number; page: number; page_size: number }
export interface BudgetRow {
  id: string; category: Category; month: string; amount: Money; notes: string | null; spent: Money; remaining: Money; utilization: string;
  status: "on_track" | "at_risk" | "exceeded";
}
export interface Recommendation {
  id: string; category: Category; month: string; proposed_amount: Money; historical_basis: Record<string, unknown> & { months: { month: string; amount: string }[]; weighted_average: string; mean: string; trend_per_month: string; months_with_data: number; method: string };
  reason: string; expected_effect: string; confidence: "low" | "medium" | "high"; limitations: string | null; status: string; created_at: string;
}
export interface Contribution { id: string; amount: Money; contribution_date: string; note: string | null; created_at: string }
export interface Goal {
  id: string; name: string; target_amount: Money; current_amount: Money; target_date: string | null; status: "active" | "completed" | "archived";
  notes: string | null; created_at: string; remaining_amount: Money; progress_percent: string; months_remaining: number | null;
  required_monthly: Money | null; on_track: boolean | null; contributions: Contribution[];
}
export interface Summary { period_start: string; period_end: string; income: Money; expenses: Money; savings: Money; savings_rate: string; transaction_count: number }
export interface CategorySlice { category_id: string; category: string; slug: string; color: string | null; amount: Money; count: number; share: string }
export interface Overview {
  month: string; total_balance: Money; summary: Summary; average_monthly_expense: Money; category_breakdown: CategorySlice[]; top_categories: CategorySlice[];
  monthly_series: { month: string; income: Money; expenses: Money; savings: Money }[]; daily_trend: { date: string; amount: Money; cumulative: Money }[];
  budgets: BudgetRow[]; goals: { id: string; name: string; target_amount: Money; current_amount: Money; progress_percent: string; remaining_amount: Money; required_monthly: Money | null; target_date: string | null }[];
  recent_transactions: TxRow[]; insights: { tone: "positive" | "neutral" | "warning"; text: string }[];
}
export interface ChatCard { type: string; [k: string]: any } // eslint-disable-line @typescript-eslint/no-explicit-any
export interface ChatMessage { id: string; role: "user" | "assistant"; content: string; meta?: { cards?: ChatCard[]; tool_events?: { tool: string; status: string }[]; error?: string; intent?: string; requires_confirmation?: boolean } | null; created_at: string; pending?: boolean }
export interface Conversation { id: string; title: string; created_at: string; updated_at: string }
