import { AnimatePresence, motion } from "framer-motion";
import {
  BarChart3, BookOpen, Feather, LayoutDashboard, LogOut, Menu, Moon, PiggyBank, ReceiptText, Settings, Sun, Wallet, X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../lib/auth";
import { useTheme } from "../../lib/theme";
import { cx } from "../ui";
import { JocastaLauncher } from "../jocasta/JocastaLauncher";
import { Logo } from "./Logo";

export const NAV = [
  { to: "/app", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/app/transactions", label: "Transactions", icon: ReceiptText },
  { to: "/app/budgets", label: "Budgets", icon: Wallet },
  { to: "/app/savings", label: "Savings Goals", icon: PiggyBank },
  { to: "/app/analytics", label: "Financial Analytics", icon: BarChart3 },
  { to: "/app/reports", label: "Reports", icon: BookOpen },
  { to: "/app/jocasta", label: "JOCASTA", icon: Feather },
  { to: "/app/settings", label: "Settings", icon: Settings },
];

export function ThemeToggle({ className }: { className?: string }) {
  const { resolved, toggle } = useTheme();
  return (
    <button onClick={toggle} className={cx("relative grid h-9 w-9 place-items-center rounded-full border border-line text-ink transition hover:border-gold/60", className)}
      aria-label={`Switch to ${resolved === "dark" ? "light" : "dark"} theme`} title="Toggle theme">
      <AnimatePresence mode="wait" initial={false}>
        <motion.span key={resolved} initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }} transition={{ duration: 0.25 }}>
          {resolved === "dark" ? <Sun className="h-4 w-4 text-gold" /> : <Moon className="h-4 w-4" />}
        </motion.span>
      </AnimatePresence>
    </button>
  );
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  return (
    <div className="flex h-full flex-col">
      <div className="px-6 pb-6 pt-7"><Logo onDark /></div>
      <div className="mx-6 mb-4 h-px bg-[rgb(var(--gold)/.35)]" />
      <nav className="flex-1 space-y-0.5 px-3" aria-label="Main">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} onClick={onNavigate}
            className={({ isActive }) => cx(
              "group relative flex items-center gap-3 rounded-md px-3 py-2.5 text-[13.5px] transition-colors",
              isActive ? "bg-white/[.07] text-[#F4F0E6]" : "text-[#F4F0E6]/65 hover:bg-white/[.04] hover:text-[#F4F0E6]",
            )}>
            {({ isActive }) => (
              <>
                {isActive && <motion.span layoutId="nav-indicator" className="absolute inset-y-1.5 left-0 w-[2px] rounded-full bg-[#C2A56E]" />}
                <Icon className={cx("h-[18px] w-[18px]", isActive ? "text-[#C2A56E]" : "text-[#F4F0E6]/55 group-hover:text-[#F4F0E6]/80")} strokeWidth={1.6} />
                <span className={label === "JOCASTA" ? "tracking-[0.14em] text-[12.5px]" : ""}>{label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="m-3 rounded-lg border border-white/10 bg-white/[.03] p-3">
        <p className="truncate text-sm text-[#F4F0E6]">{user?.full_name}</p>
        <p className="truncate text-xs text-[#F4F0E6]/50">{user?.email}</p>
        <button onClick={async () => { await logout(); nav("/"); }} className="mt-3 flex items-center gap-2 text-xs text-[#F4F0E6]/70 hover:text-[#C2A56E]">
          <LogOut className="h-3.5 w-3.5" /> Sign out
        </button>
      </div>
    </div>
  );
}

export function AppLayout() {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => { setOpen(false); window.scrollTo(0, 0); }, [loc.pathname]);
  const current = NAV.find((n) => (n.end ? loc.pathname === n.to : loc.pathname.startsWith(n.to)));

  return (
    <div className="min-h-screen bg-bg">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-card focus:px-3 focus:py-2">Skip to content</a>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 bg-[#1F3026] dark:bg-[#111713] lg:block" style={{ backgroundImage: "linear-gradient(180deg, rgba(255,255,255,.02), transparent 40%)" }}>
        <Sidebar />
      </aside>
      <AnimatePresence>
        {open && (
          <>
            <motion.div className="fixed inset-0 z-40 bg-black/50 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setOpen(false)} />
            <motion.aside className="fixed inset-y-0 left-0 z-50 w-72 bg-[#1F3026] dark:bg-[#111713] lg:hidden" initial={{ x: -300 }} animate={{ x: 0 }} exit={{ x: -300 }} transition={{ type: "spring", damping: 30, stiffness: 300 }}>
              <button className="absolute right-3 top-6 rounded p-1 text-[#F4F0E6]/70" onClick={() => setOpen(false)} aria-label="Close menu"><X className="h-5 w-5" /></button>
              <Sidebar onNavigate={() => setOpen(false)} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 border-b border-line/70 bg-bg/85 backdrop-blur">
          <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-8">
            <div className="flex items-center gap-3">
              <button className="rounded-md p-2 text-ink lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><Menu className="h-5 w-5" /></button>
              <p className="font-serif text-lg italic text-muted">{current?.label ?? "FinanceMate"}</p>
            </div>
            <div className="flex items-center gap-3">
              <span className="hidden text-xs text-muted sm:block">{new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })}</span>
              <ThemeToggle />
            </div>
          </div>
        </header>
        <main id="main" className="mx-auto max-w-7xl px-4 pb-28 pt-8 sm:px-8">
          <motion.div key={loc.pathname} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}>
            <Outlet />
          </motion.div>
        </main>
      </div>
      {!loc.pathname.startsWith("/app/jocasta") && <JocastaLauncher />}
    </div>
  );
}
