import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

export type ThemePref = "light" | "dark" | "system";
type Ctx = { pref: ThemePref; resolved: "light" | "dark"; setPref: (p: ThemePref) => void; toggle: () => void };
const ThemeContext = createContext<Ctx | null>(null);
const KEY = "fm-theme";

const systemDark = () => typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches;
const readPref = (): ThemePref => {
  try { const v = localStorage.getItem(KEY); return v === "light" || v === "dark" ? v : "system"; } catch { return "system"; }
};

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [pref, setPrefState] = useState<ThemePref>(readPref);
  const [sys, setSys] = useState<boolean>(systemDark());
  const resolved = pref === "system" ? (sys ? "dark" : "light") : pref;

  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    const on = (e: MediaQueryListEvent) => setSys(e.matches);
    mq?.addEventListener?.("change", on);
    return () => mq?.removeEventListener?.("change", on);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", resolved);
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", resolved === "dark" ? "#151B17" : "#25382D");
  }, [resolved]);

  const setPref = useCallback((p: ThemePref) => {
    setPrefState(p);
    try { localStorage.setItem(KEY, p); } catch { /* ignore */ }
  }, []);
  const toggle = useCallback(() => setPref(resolved === "dark" ? "light" : "dark"), [resolved, setPref]);

  return <ThemeContext.Provider value={{ pref, resolved, setPref, toggle }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside ThemeProvider");
  return ctx;
}
