import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { BudgetRow, Category, Goal, Overview, Page, Recommendation, Summary, Transaction } from "../types";

export const keys = {
  categories: ["categories"] as const,
  overview: (m: string) => ["overview", m] as const,
  transactions: (p: object) => ["transactions", p] as const,
  budgets: (m: string) => ["budgets", m] as const,
  recs: (m: string) => ["recommendations", m] as const,
  goals: ["goals"] as const,
};

/** Any data mutation (manual or via JOCASTA) invalidates everything derived from records. */
export function useInvalidateFinance() {
  const qc = useQueryClient();
  return () => {
    for (const k of ["overview", "transactions", "budgets", "recommendations", "goals", "analytics", "report", "duplicates"]) qc.invalidateQueries({ queryKey: [k] });
  };
}

export const useCategories = () => useQuery({ queryKey: keys.categories, queryFn: () => api<Category[]>("/categories"), staleTime: 5 * 60_000 });

export const useOverview = (month: string, months = 6) =>
  useQuery({ queryKey: [...keys.overview(month), months], queryFn: () => api<Overview>("/analytics/overview", { params: { month, months } }) });

export type TxFilters = { search?: string; category_id?: string; type?: string; start_date?: string; end_date?: string; sort?: string; order?: string; page?: number; page_size?: number };
export const useTransactions = (f: TxFilters) =>
  useQuery({ queryKey: keys.transactions(f), queryFn: () => api<Page<Transaction>>("/transactions", { params: f as Record<string, string> }), placeholderData: (prev) => prev });

export type BudgetResponse = { month: string; items: BudgetRow[]; previous_month: BudgetRow[]; totals: { budgeted: string; spent: string; remaining: string; utilization: string } };
export const useBudgets = (month: string) => useQuery({ queryKey: keys.budgets(month), queryFn: () => api<BudgetResponse>("/budgets", { params: { month } }) });
export const useRecommendations = (month: string) =>
  useQuery({ queryKey: keys.recs(month), queryFn: () => api<Recommendation[]>("/budgets/recommendations", { params: { month } }) });

export const useGoals = () => useQuery({ queryKey: keys.goals, queryFn: () => api<Goal[]>("/savings") });

export const useSummary = (start: string, end: string) =>
  useQuery({ queryKey: ["analytics", "summary", start, end], queryFn: () => api<Summary>("/analytics/summary", { params: { start_date: start, end_date: end } }) });

export function useFinanceMutation<TVars = void, TRes = unknown>(fn: (v: TVars) => Promise<TRes>) {
  const invalidate = useInvalidateFinance();
  return useMutation({ mutationFn: fn, onSuccess: () => invalidate() });
}
