/** Thin fetch wrapper. The API base URL is public config; no secrets ever live in the frontend. */
export const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") || "http://localhost:8000/api/v1";

const TOKEN_KEY = "fm-token";

export const tokenStore = {
  get: () => {
    try { return sessionStorage.getItem(TOKEN_KEY); } catch { return null; }
  },
  set: (t: string) => { try { sessionStorage.setItem(TOKEN_KEY, t); } catch { /* ignore */ } },
  clear: () => { try { sessionStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ } },
};

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;
  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: () => void) { onUnauthorized = fn; }

type Opts = { method?: string; body?: unknown; form?: FormData; params?: Record<string, string | number | boolean | undefined | null>; raw?: boolean; timeoutMs?: number };

export async function api<T = unknown>(path: string, opts: Opts = {}): Promise<T> {
  const url = new URL(API_BASE + path);
  Object.entries(opts.params || {}).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v)); });
  const headers: Record<string, string> = {};
  const token = tokenStore.get();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), opts.timeoutMs ?? 60000);
  let res: Response;
  try {
    res = await fetch(url, {
      method: opts.method || (opts.body !== undefined || opts.form ? "POST" : "GET"),
      headers,
      body: opts.form ?? (opts.body !== undefined ? JSON.stringify(opts.body) : undefined),
      signal: ctrl.signal,
    });
  } catch (e) {
    const aborted = (e as Error).name === "AbortError";
    throw new ApiError(0, aborted ? "timeout" : "network",
      aborted ? "The server took too long to respond. Free-tier servers may be waking up — please retry."
              : "Can't reach the FinanceMate server. It may be starting up; please retry in a moment.");
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 401 && token) onUnauthorized?.();
  if (!res.ok) {
    let code = "http_error", message = `Request failed (${res.status})`, details: unknown;
    try {
      const data = await res.json();
      if (data?.error) ({ code, message, details } = data.error);
      else if (data?.detail) message = typeof data.detail === "string" ? data.detail : message;
    } catch { /* non-JSON */ }
    if (res.status === 429) message = "Too many requests. Please slow down and try again shortly.";
    throw new ApiError(res.status, code, message, details);
  }
  if (res.status === 204) return undefined as T;
  if (opts.raw) return (await res.blob()) as T;
  return (await res.json()) as T;
}

export async function download(path: string, params: Opts["params"], fallbackName: string) {
  const url = new URL(API_BASE + path);
  Object.entries(params || {}).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v)); });
  const res = await fetch(url, { headers: { Authorization: `Bearer ${tokenStore.get() ?? ""}` } });
  if (!res.ok) throw new ApiError(res.status, "download_failed", "Download failed");
  const blob = await res.blob();
  const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") || "")?.[1] || fallbackName;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
