import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowDown, ArrowUp, Copy, Download, FileUp, Pencil, Plus, ReceiptText, Repeat, Search, Trash2, Upload } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { Badge, Button, Card, ConfirmDialog, EmptyState, ErrorState, Input, Modal, PageHeader, Select, Skeleton, Textarea, cx, errMsg, useToast } from "../components/ui";
import { api, download } from "../lib/api";
import { useAuth } from "../lib/auth";
import { currencySymbol, fmtDate, money, num, todayISO } from "../lib/format";
import { useCategories, useFinanceMutation, useTransactions, type TxFilters } from "../lib/queries";
import type { Transaction, TxRow } from "../types";

const txSchema = z.object({
  description: z.string().trim().min(1, "Description is required").max(255),
  amount: z.string().regex(/^\d{1,12}(\.\d{1,2})?$/, "Enter a positive amount with up to 2 decimals").refine((v) => Number(v) > 0, "Must be greater than zero"),
  type: z.enum(["expense", "income"]),
  category_id: z.string().optional(),
  transaction_date: z.string().min(1, "Date is required"),
  payment_method: z.string().max(40).optional(),
  notes: z.string().max(2000).optional(),
  is_recurring: z.boolean(),
  recurrence_interval: z.string().optional(),
}).refine((d) => !d.is_recurring || !!d.recurrence_interval, { path: ["recurrence_interval"], message: "Choose how often it repeats" });
type TxForm = z.infer<typeof txSchema>;

export function TransactionModal({ open, onClose, tx }: { open: boolean; onClose: () => void; tx?: Transaction | null }) {
  const { user } = useAuth();
  const toast = useToast();
  const { data: cats } = useCategories();
  const defaults: TxForm = useMemo(() => tx ? {
    description: tx.description, amount: tx.amount, type: tx.type, category_id: tx.category.id, transaction_date: tx.transaction_date,
    payment_method: tx.payment_method || "", notes: tx.notes || "", is_recurring: tx.is_recurring, recurrence_interval: tx.recurrence_interval || "",
  } : { description: "", amount: "", type: "expense", category_id: "", transaction_date: todayISO(), payment_method: "", notes: "", is_recurring: false, recurrence_interval: "" }, [tx]);
  const { register, handleSubmit, reset, watch, formState: { errors } } = useForm<TxForm>({ resolver: zodResolver(txSchema), defaultValues: defaults });
  useEffect(() => { if (open) reset(defaults); }, [open, defaults, reset]);
  const type = watch("type");
  const recurring = watch("is_recurring");
  const save = useFinanceMutation((v: TxForm) => {
    const body = { ...v, category_id: v.category_id || null, payment_method: v.payment_method || null, notes: v.notes || null, recurrence_interval: v.is_recurring ? v.recurrence_interval : null };
    return tx ? api(`/transactions/${tx.id}`, { method: "PATCH", body }) : api("/transactions", { body });
  });
  const submit = handleSubmit(async (v) => {
    try { await save.mutateAsync(v); toast.success(tx ? "Transaction updated" : "Transaction added"); onClose(); }
    catch (e) { toast.error(errMsg(e)); }
  });
  const options = (cats || []).filter((c) => c.kind === "both" || c.kind === type);
  return (
    <Modal open={open} onClose={onClose} title={tx ? "Edit transaction" : "New transaction"}
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button onClick={submit} loading={save.isPending}>{tx ? "Save changes" : "Add transaction"}</Button></>}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <div className="grid grid-cols-2 gap-2 rounded-lg bg-bg2 p-1" role="radiogroup" aria-label="Type">
          {(["expense", "income"] as const).map((t) => (
            <label key={t} className={cx("cursor-pointer rounded-md py-2 text-center text-sm capitalize transition", type === t ? "bg-card shadow-soft text-ink" : "text-muted")}>
              <input type="radio" value={t} className="sr-only" {...register("type")} />{t}
            </label>
          ))}
        </div>
        <Input label="Description" placeholder="e.g. Groceries at DMart" {...register("description")} error={errors.description?.message} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label={`Amount (${currencySymbol(user?.currency || "INR")})`} inputMode="decimal" placeholder="0.00" {...register("amount")} error={errors.amount?.message} />
          <Input label="Date" type="date" {...register("transaction_date")} error={errors.transaction_date?.message} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Select label="Category" {...register("category_id")}>
            <option value="">Auto-categorise</option>
            {options.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
          <Select label="Payment method" {...register("payment_method")}>
            <option value="">—</option>{["UPI", "Card", "Cash", "NetBanking", "Wallet", "Cheque"].map((p) => <option key={p}>{p}</option>)}
          </Select>
        </div>
        <Textarea label="Notes" rows={2} {...register("notes")} />
        <div className="flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-[rgb(var(--forest))]" {...register("is_recurring")} /> Recurring</label>
          {recurring && (
            <Select aria-label="Repeats" {...register("recurrence_interval")} error={errors.recurrence_interval?.message} className="w-40">
              <option value="">Repeats…</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option><option value="yearly">Yearly</option>
            </Select>
          )}
        </div>
      </form>
    </Modal>
  );
}

type Preview = { upload_id: string; filename: string; rows: { index: number; transaction_date: string; description: string; amount: string; type: string; category_slug: string; category_name: string; categorization_source: string; confidence: string; is_duplicate: boolean; duplicate_reason: string | null }[]; duplicates: number; warnings: string[] };

export function ImportModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { user } = useAuth();
  const cur = user?.currency || "INR";
  const toast = useToast();
  const { data: cats } = useCategories();
  const [preview, setPreview] = useState<Preview | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [overrides, setOverrides] = useState<Record<number, string>>({});
  const [uploading, setUploading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const approve = useFinanceMutation(() => api<{ imported: number; skipped: number }>(`/uploads/statements/${preview!.upload_id}/approve`, { body: { selected_indexes: [...selected], category_overrides: overrides } }));

  useEffect(() => { if (!open) { setPreview(null); setSelected(new Set()); setOverrides({}); setErr(null); } }, [open]);

  const upload = async (file: File) => {
    setErr(null);
    if (file.size > 10 * 1024 * 1024) { setErr("File exceeds the 10 MB limit."); return; }
    const form = new FormData();
    form.append("file", file);
    setUploading(true);
    try {
      const p = await api<Preview>("/uploads/statements", { form, timeoutMs: 120000 });
      setPreview(p);
      setSelected(new Set(p.rows.filter((r) => !r.is_duplicate).map((r) => r.index)));
    } catch (e) { setErr(errMsg(e)); } finally { setUploading(false); }
  };
  const reject = async () => { if (preview) await api(`/uploads/statements/${preview.upload_id}/reject`, { method: "POST" }).catch(() => undefined); onClose(); };
  const commit = async () => {
    try { const r = await approve.mutateAsync(); toast.success(`Imported ${r.imported} transaction${r.imported === 1 ? "" : "s"}`); onClose(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const toggle = (i: number) => setSelected((s) => { const n = new Set(s); if (n.has(i)) n.delete(i); else n.add(i); return n; });

  return (
    <Modal open={open} onClose={preview ? reject : onClose} title="Import bank statement" wide
      footer={preview ? <><Button variant="secondary" onClick={reject}>Reject import</Button><Button onClick={commit} loading={approve.isPending} disabled={!selected.size}>Approve {selected.size} transaction{selected.size === 1 ? "" : "s"}</Button></> : undefined}>
      {!preview ? (
        <div>
          <button onClick={() => fileRef.current?.click()} disabled={uploading}
            onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) upload(f); }}
            className="flex w-full flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-line px-6 py-14 text-center transition hover:border-gold/60 hover:bg-bg2/40">
            <FileUp className={cx("h-9 w-9 text-gold", uploading && "animate-bounce")} strokeWidth={1.4} />
            <span className="font-serif text-xl">{uploading ? "Reading your statement…" : "Drop a statement here, or choose a file"}</span>
            <span className="text-xs text-muted">CSV, XLSX or text-based PDF · up to 10 MB · scanned PDFs are not supported</span>
          </button>
          <input ref={fileRef} type="file" accept=".csv,.xlsx,.pdf" className="hidden" aria-label="Statement file" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ""; }} />
          {err && <p role="alert" className="mt-4 rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">{err}</p>}
          <p className="mt-4 text-xs text-muted">Your file is processed temporarily and deleted immediately. Nothing is saved until you approve the preview.</p>
        </div>
      ) : (
        <div>
          <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium">{preview.filename}</span><Badge>{preview.rows.length} rows</Badge>
            {preview.duplicates > 0 && <Badge tone="warning">{preview.duplicates} possible duplicates (unselected)</Badge>}
          </div>
          {preview.warnings.map((w) => <p key={w} className="mb-2 text-xs text-muted">• {w}</p>)}
          <div className="max-h-[50vh] overflow-auto rounded-lg border border-line">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-bg2 text-left text-[11px] uppercase tracking-wider text-muted">
                <tr><th className="p-2"><input type="checkbox" aria-label="Select all" checked={selected.size === preview.rows.length} onChange={(e) => setSelected(e.target.checked ? new Set(preview.rows.map((r) => r.index)) : new Set())} /></th>
                  <th className="p-2">Date</th><th className="p-2">Description</th><th className="p-2">Category</th><th className="p-2 text-right">Amount</th></tr>
              </thead>
              <tbody className="divide-y divide-line">
                {preview.rows.map((r) => (
                  <tr key={r.index} className={cx(r.is_duplicate && "bg-[#b9832f]/5", !selected.has(r.index) && "opacity-60")}>
                    <td className="p-2"><input type="checkbox" checked={selected.has(r.index)} onChange={() => toggle(r.index)} aria-label={`Select ${r.description}`} /></td>
                    <td className="whitespace-nowrap p-2 tabular">{fmtDate(r.transaction_date)}</td>
                    <td className="p-2">{r.description}{r.is_duplicate && <span className="ml-2"><Badge tone="warning">{r.duplicate_reason}</Badge></span>}</td>
                    <td className="p-2">
                      <select className="input h-8 py-0 text-xs" value={overrides[r.index] || ""} onChange={(e) => setOverrides((o) => ({ ...o, [r.index]: e.target.value }))} aria-label="Category">
                        <option value="">{r.category_name}</option>
                        {(cats || []).filter((c) => c.slug !== r.category_slug).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                      </select>
                      <span className="mt-0.5 block text-[10px] text-muted">{overrides[r.index] ? "your choice" : `${r.categorization_source} · ${Math.round(num(r.confidence) * 100)}% confidence`}</span>
                    </td>
                    <td className={cx("whitespace-nowrap p-2 text-right tabular", r.type === "income" && "text-success")}>{r.type === "income" ? "+" : "−"}{money(r.amount, cur)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Modal>
  );
}

function SortHeader({ label, field, f, setF, className }: { label: string; field: string; f: TxFilters; setF: (f: TxFilters) => void; className?: string }) {
  const active = f.sort === field;
  return (
    <th className={cx("p-3 font-medium", className)}>
      <button onClick={() => setF({ ...f, sort: field, order: active && f.order === "desc" ? "asc" : "desc", page: 1 })} className="inline-flex items-center gap-1 hover:text-ink" aria-label={`Sort by ${label}`}>
        {label}{active && (f.order === "asc" ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />)}
      </button>
    </th>
  );
}

export default function Transactions() {
  const { user } = useAuth();
  const cur = user?.currency || "INR";
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const [f, setF] = useState<TxFilters>({ sort: "date", order: "desc", page: 1, page_size: 20 });
  const [searchText, setSearchText] = useState("");
  const [editing, setEditing] = useState<Transaction | null>(null);
  const [adding, setAdding] = useState(false);
  const [importing, setImporting] = useState(params.get("import") === "1");
  const [deleting, setDeleting] = useState<Transaction | null>(null);
  const { data: cats } = useCategories();
  const { data, isLoading, error, refetch, isFetching } = useTransactions(f);
  const { data: dups } = useQuery({ queryKey: ["duplicates"], queryFn: () => api<{ groups: TxRow[][] }>("/transactions/duplicates") });
  const del = useFinanceMutation((id: string) => api(`/transactions/${id}`, { method: "DELETE" }));
  const recurring = useFinanceMutation(() => api<{ created: number }>("/transactions/recurring/run", { method: "POST" }));

  useEffect(() => { const t = setTimeout(() => setF((p) => ({ ...p, search: searchText || undefined, page: 1 })), 300); return () => clearTimeout(t); }, [searchText]);
  useEffect(() => { if (!importing && params.get("import")) setParams({}, { replace: true }); }, [importing, params, setParams]);

  const pages = data ? Math.max(1, Math.ceil(data.total / (f.page_size || 20))) : 1;
  const exportCsv = () => download("/transactions/export", { ...f, page: undefined, page_size: undefined }, "transactions.csv").catch((e) => toast.error(errMsg(e)));

  return (
    <>
      <PageHeader eyebrow="The ledger" title="Transactions" subtitle="Every entry, searchable and sortable. Categories show how they were assigned."
        actions={<>
          <Button variant="secondary" onClick={() => setImporting(true)}><Upload className="h-4 w-4" /> Import</Button>
          <Button variant="secondary" onClick={exportCsv}><Download className="h-4 w-4" /> CSV</Button>
          <Button onClick={() => setAdding(true)}><Plus className="h-4 w-4" /> Add</Button>
        </>} />

      {!!dups?.groups.length && (
        <div className="mb-4 flex items-center gap-3 rounded-lg border border-[#b9832f]/40 bg-[#b9832f]/5 px-4 py-3 text-sm">
          <Copy className="h-4 w-4 text-[#b9832f]" />
          <span>{dups.groups.length} set{dups.groups.length > 1 ? "s" : ""} of possible duplicate transactions: {dups.groups.slice(0, 3).map((g) => `${g[0].description} (${fmtDate(g[0].date)})`).join(", ")}.</span>
          <button className="ml-auto text-xs text-gold hover:underline" onClick={() => setSearchText(dups.groups[0][0].description)}>Review</button>
        </div>
      )}

      <Card className="!p-0">
        <div className="grid gap-3 border-b border-line p-4 md:grid-cols-[1.5fr,1fr,0.8fr,0.9fr,0.9fr,auto]">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <input className="input pl-9" placeholder="Search description, notes, category…" value={searchText} onChange={(e) => setSearchText(e.target.value)} aria-label="Search transactions" />
          </div>
          <Select aria-label="Category filter" value={f.category_id || ""} onChange={(e) => setF({ ...f, category_id: e.target.value || undefined, page: 1 })}>
            <option value="">All categories</option>{(cats || []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
          <Select aria-label="Type filter" value={f.type || ""} onChange={(e) => setF({ ...f, type: e.target.value || undefined, page: 1 })}>
            <option value="">All types</option><option value="expense">Expenses</option><option value="income">Income</option>
          </Select>
          <input type="date" className="input" aria-label="From date" value={f.start_date || ""} onChange={(e) => setF({ ...f, start_date: e.target.value || undefined, page: 1 })} />
          <input type="date" className="input" aria-label="To date" value={f.end_date || ""} onChange={(e) => setF({ ...f, end_date: e.target.value || undefined, page: 1 })} />
          <Button variant="ghost" size="sm" className="h-10" onClick={async () => { const r = await recurring.mutateAsync(); toast.info(r.created ? `Added ${r.created} recurring entries` : "Recurring entries are up to date"); }} title="Generate due recurring transactions">
            <Repeat className="h-4 w-4" /><span className="md:hidden xl:inline">Recurring</span>
          </Button>
        </div>

        {error ? <div className="p-6"><ErrorState error={error} onRetry={refetch} /></div> : isLoading ? (
          <div className="space-y-2 p-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
        ) : !data?.items.length ? (
          <div className="p-6"><EmptyState icon={<ReceiptText className="h-8 w-8" />} title="No transactions found" text={f.search || f.category_id || f.type || f.start_date ? "Try adjusting the filters." : "Add your first transaction or import a statement."}
            action={<Button onClick={() => setAdding(true)}><Plus className="h-4 w-4" /> Add transaction</Button>} /></div>
        ) : (
          <>
            {/* desktop table */}
            <div className={cx("hidden overflow-x-auto md:block", isFetching && "opacity-70")}>
              <table className="w-full text-sm">
                <thead className="border-b border-line text-left text-[11px] uppercase tracking-wider text-muted">
                  <tr>
                    <SortHeader label="Date" field="date" f={f} setF={setF} />
                    <SortHeader label="Description" field="description" f={f} setF={setF} />
                    <th className="p-3 font-medium">Category</th><th className="p-3 font-medium">Method</th>
                    <SortHeader label="Amount" field="amount" f={f} setF={setF} className="text-right" />
                    <th className="p-3"><span className="sr-only">Actions</span></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {data.items.map((t) => (
                    <tr key={t.id} className="group transition hover:bg-bg2/40">
                      <td className="whitespace-nowrap p-3 tabular text-muted">{fmtDate(t.transaction_date)}</td>
                      <td className="p-3"><span className="text-ink">{t.description}</span>{t.is_recurring && <Repeat className="ml-1.5 inline h-3 w-3 text-gold" aria-label="recurring" />}{t.notes && <span className="block max-w-xs truncate text-[11px] text-muted">{t.notes}</span>}</td>
                      <td className="p-3">
                        <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: t.category.color || "#8A8577" }} />{t.category.name}</span>
                        {t.categorization_source !== "user" && <span className={cx("block text-[10px]", num(t.categorization_confidence) < 0.5 ? "text-danger" : "text-muted")}>{t.categorization_source} · {Math.round(num(t.categorization_confidence) * 100)}%</span>}
                      </td>
                      <td className="p-3 text-muted">{t.payment_method || "—"}</td>
                      <td className={cx("whitespace-nowrap p-3 text-right font-medium tabular", t.type === "income" ? "text-success" : "text-ink")}>{t.type === "income" ? "+" : "−"}{money(t.amount, cur)}</td>
                      <td className="whitespace-nowrap p-3 text-right">
                        <button className="rounded p-1.5 text-muted opacity-60 hover:bg-bg2 hover:text-ink group-hover:opacity-100" onClick={() => setEditing(t)} aria-label={`Edit ${t.description}`}><Pencil className="h-4 w-4" /></button>
                        <button className="rounded p-1.5 text-muted opacity-60 hover:bg-danger/10 hover:text-danger group-hover:opacity-100" onClick={() => setDeleting(t)} aria-label={`Delete ${t.description}`}><Trash2 className="h-4 w-4" /></button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {/* mobile list */}
            <ul className="divide-y divide-line md:hidden">
              {data.items.map((t) => (
                <li key={t.id} className="flex items-center gap-3 p-4">
                  <span className="h-9 w-1 shrink-0 rounded-full" style={{ background: t.category.color || "#8A8577" }} />
                  <button className="min-w-0 flex-1 text-left" onClick={() => setEditing(t)}>
                    <p className="truncate text-sm">{t.description}</p>
                    <p className="text-[11px] text-muted">{t.category.name} · {fmtDate(t.transaction_date)}</p>
                  </button>
                  <span className={cx("text-sm tabular", t.type === "income" && "text-success")}>{t.type === "income" ? "+" : "−"}{money(t.amount, cur)}</span>
                  <button onClick={() => setDeleting(t)} className="p-1 text-muted" aria-label={`Delete ${t.description}`}><Trash2 className="h-4 w-4" /></button>
                </li>
              ))}
            </ul>
            <div className="flex items-center justify-between border-t border-line px-4 py-3 text-xs text-muted">
              <span>{data.total} transaction{data.total === 1 ? "" : "s"}</span>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="secondary" disabled={(f.page || 1) <= 1} onClick={() => setF({ ...f, page: (f.page || 1) - 1 })}>Previous</Button>
                <span>Page {f.page} of {pages}</span>
                <Button size="sm" variant="secondary" disabled={(f.page || 1) >= pages} onClick={() => setF({ ...f, page: (f.page || 1) + 1 })}>Next</Button>
              </div>
            </div>
          </>
        )}
      </Card>

      <TransactionModal open={adding || !!editing} tx={editing} onClose={() => { setAdding(false); setEditing(null); }} />
      <ImportModal open={importing} onClose={() => setImporting(false)} />
      <ConfirmDialog open={!!deleting} title="Delete transaction" onClose={() => setDeleting(null)} loading={del.isPending}
        message={deleting && <>Delete <strong>{deleting.description}</strong> ({money(deleting.amount, cur)}, {fmtDate(deleting.transaction_date)})? It will be removed from all totals and reports.</>}
        onConfirm={async () => { try { await del.mutateAsync(deleting!.id); toast.success("Transaction deleted"); setDeleting(null); } catch (e) { toast.error(errMsg(e)); } }} />
    </>
  );
}
