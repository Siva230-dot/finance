import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { ToastProvider } from "../components/ui";
import { AuthProvider } from "../lib/auth";
import { ThemeProvider } from "../lib/theme";

type Handler = (url: URL, init: RequestInit) => { status?: number; body?: unknown } | undefined;

/** Install a fetch mock routing by "METHOD /path". Returns the list of recorded calls. */
export function mockApi(routes: Record<string, Handler | object>) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input));
    const method = (init.method || "GET").toUpperCase();
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const body = typeof init.body === "string" ? JSON.parse(init.body) : init.body;
    calls.push({ method, path, body });
    const key = Object.keys(routes).find((k) => {
      const [m, p] = k.split(" ");
      return m === method && new RegExp("^" + p.replace(/:\w+/g, "[^/]+") + "$").test(path);
    });
    if (!key) return new Response(JSON.stringify({ error: { code: "not_found", message: `No mock for ${method} ${path}` } }), { status: 404 });
    const r = routes[key];
    const out = typeof r === "function" ? (r as Handler)(url, init) || {} : { body: r };
    return new Response(out.status === 204 ? null : JSON.stringify(out.body ?? {}), { status: out.status ?? 200, headers: { "Content-Type": "application/json" } });
  }) as typeof fetch;
  return calls;
}

export function renderApp(ui: ReactElement, { route = "/" } = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ThemeProvider>
        <MemoryRouter initialEntries={[route]}>
          <AuthProvider>
            <ToastProvider>{ui}</ToastProvider>
          </AuthProvider>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

export const USER = { id: "u1", email: "a@example.com", full_name: "Asha Rao", currency: "INR", theme_preference: "system", created_at: "2026-01-01T00:00:00Z" };
