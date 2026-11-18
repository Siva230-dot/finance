const LOCALE: Record<string, string> = { INR: "en-IN", USD: "en-US", EUR: "de-DE", GBP: "en-GB", JPY: "ja-JP", AUD: "en-AU", CAD: "en-CA", SGD: "en-SG", AED: "en-AE", CHF: "de-CH" };

/** Display-only formatting. Values arrive as exact decimal strings and are only converted for rendering. */
export function money(value: string | number | null | undefined, currency = "INR", opts: { compact?: boolean; sign?: boolean; decimals?: boolean } = {}) {
  const n = typeof value === "number" ? value : Number(value ?? 0);
  const fmt = new Intl.NumberFormat(LOCALE[currency] || "en-IN", {
    style: "currency", currency, notation: opts.compact ? "compact" : "standard",
    minimumFractionDigits: opts.compact ? 0 : opts.decimals === false ? 0 : 2,
    maximumFractionDigits: opts.compact ? 1 : opts.decimals === false ? 0 : 2,
  });
  const s = fmt.format(Math.abs(n));
  if (n < 0) return `−${s}`;
  return opts.sign && n > 0 ? `+${s}` : s;
}

export const num = (v: string | number | null | undefined) => Number(v ?? 0);

export function fmtDate(iso: string, style: "short" | "long" | "month" = "short") {
  const d = new Date(iso.length === 10 ? iso + "T00:00:00" : iso);
  if (style === "month") return d.toLocaleDateString("en-GB", { month: "long", year: "numeric" });
  if (style === "long") return d.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function monthKey(d = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

export function shiftMonth(key: string, delta: number) {
  const [y, m] = key.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return monthKey(d);
}

export function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export const currencySymbol = (c: string) => ({ INR: "₹", USD: "$", EUR: "€", GBP: "£", JPY: "¥" } as Record<string, string>)[c] || c;
