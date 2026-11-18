import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, setUnauthorizedHandler, tokenStore } from "./api";
import type { User } from "../types";

type AuthCtx = {
  user: User | null; loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: { email: string; full_name: string; password: string; currency: string }) => Promise<void>;
  logout: () => Promise<void>;
  setUser: (u: User) => void;
  setToken: (t: string) => void;
};
const Ctx = createContext<AuthCtx | null>(null);
type TokenResponse = { access_token: string; user: User };

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(!!tokenStore.get());
  const qc = useQueryClient();

  const clear = useCallback(() => { tokenStore.clear(); setUser(null); qc.clear(); }, [qc]);

  useEffect(() => {
    setUnauthorizedHandler(clear);
    if (!tokenStore.get()) return;
    api<User>("/users/me").then(setUser).catch(clear).finally(() => setLoading(false));
  }, [clear]);

  const accept = (r: TokenResponse) => { tokenStore.set(r.access_token); setUser(r.user); };
  const login = async (email: string, password: string) => accept(await api<TokenResponse>("/auth/login", { body: { email, password } }));
  const register = async (data: { email: string; full_name: string; password: string; currency: string }) =>
    accept(await api<TokenResponse>("/auth/register", { body: data }));
  const logout = async () => { try { await api("/auth/logout", { method: "POST" }); } catch { /* token may already be invalid */ } clear(); };

  return <Ctx.Provider value={{ user, loading, login, register, logout, setUser, setToken: tokenStore.set }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth must be used inside AuthProvider");
  return c;
}
