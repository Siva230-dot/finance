import { Download, Monitor, Moon, Sun, Trash2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Card, Input, Modal, PageHeader, Select, cx, errMsg, useToast } from "../components/ui";
import { api, download, tokenStore } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useInvalidateFinance } from "../lib/queries";
import { useTheme, type ThemePref } from "../lib/theme";
import type { User } from "../types";

const CURRENCIES = ["INR", "USD", "EUR", "GBP", "JPY", "AUD", "CAD", "SGD", "AED", "CHF"];

export default function Settings() {
  const { user, setUser, logout } = useAuth();
  const { pref, setPref } = useTheme();
  const toast = useToast();
  const nav = useNavigate();
  const invalidate = useInvalidateFinance();
  const [name, setName] = useState(user?.full_name || "");
  const [currency, setCurrency] = useState(user?.currency || "INR");
  const [savingProfile, setSavingProfile] = useState(false);
  const [pw, setPw] = useState({ current: "", next: "", confirm: "" });
  const [pwErr, setPwErr] = useState<string | null>(null);
  const [pwBusy, setPwBusy] = useState(false);
  const [del, setDel] = useState({ open: false, password: "", confirm: "", busy: false, err: "" });

  const saveProfile = async () => {
    setSavingProfile(true);
    try { const u = await api<User>("/users/me", { method: "PATCH", body: { full_name: name, currency } }); setUser(u); invalidate(); toast.success("Profile saved"); }
    catch (e) { toast.error(errMsg(e)); } finally { setSavingProfile(false); }
  };
  const chooseTheme = async (p: ThemePref) => {
    setPref(p);
    try { const u = await api<User>("/users/me", { method: "PATCH", body: { theme_preference: p } }); setUser(u); } catch { /* local preference still applies */ }
  };
  const changePassword = async () => {
    setPwErr(null);
    if (pw.next.length < 8 || !/\d/.test(pw.next) || !/[A-Za-z]/.test(pw.next)) return setPwErr("New password needs 8+ characters with letters and numbers");
    if (pw.next !== pw.confirm) return setPwErr("Passwords do not match");
    setPwBusy(true);
    try {
      const r = await api<{ access_token: string }>("/users/me/password", { body: { current_password: pw.current, new_password: pw.next } });
      tokenStore.set(r.access_token);
      setPw({ current: "", next: "", confirm: "" });
      toast.success("Password changed. Other sessions were signed out.");
    } catch (e) { setPwErr(errMsg(e)); } finally { setPwBusy(false); }
  };
  const deleteAccount = async () => {
    setDel((d) => ({ ...d, busy: true, err: "" }));
    try { await api("/users/me", { method: "DELETE", body: { password: del.password, confirm: del.confirm } }); await logout().catch(() => undefined); nav("/"); }
    catch (e) { setDel((d) => ({ ...d, busy: false, err: errMsg(e) })); }
  };

  return (
    <>
      <PageHeader eyebrow="Preferences" title="Settings" subtitle="Your profile, appearance, security and data." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card eyebrow="Personal information" title="Profile">
          <div className="space-y-4">
            <Input label="Full name" value={name} onChange={(e) => setName(e.target.value)} />
            <Input label="Email" value={user?.email || ""} disabled hint="Email cannot be changed." />
            <Select label="Currency" value={currency} onChange={(e) => setCurrency(e.target.value)}>{CURRENCIES.map((c) => <option key={c}>{c}</option>)}</Select>
            <p className="text-xs text-muted">Changing currency changes how amounts are displayed; stored values are not converted.</p>
            <Button onClick={saveProfile} loading={savingProfile} disabled={!name.trim()}>Save profile</Button>
          </div>
        </Card>
        <Card eyebrow="Appearance" title="Theme">
          <div className="grid grid-cols-3 gap-3" role="radiogroup" aria-label="Theme">
            {([["light", "Light", Sun], ["dark", "Dark", Moon], ["system", "System", Monitor]] as const).map(([k, label, Icon]) => (
              <button key={k} role="radio" aria-checked={pref === k} onClick={() => chooseTheme(k)}
                className={cx("flex flex-col items-center gap-2 rounded-xl border p-4 transition", pref === k ? "border-gold bg-gold/5 shadow-soft" : "border-line hover:border-gold/50")}>
                <span className={cx("grid h-14 w-full place-items-center rounded-md border", k === "dark" ? "border-[#43483D] bg-[#151B17]" : k === "light" ? "border-[#D9D0BF] bg-[#F4F0E6]" : "border-line bg-gradient-to-r from-[#F4F0E6] to-[#151B17]")}>
                  <Icon className={cx("h-5 w-5", k === "dark" ? "text-[#B99B63]" : "text-[#25382D]")} />
                </span>
                <span className="text-sm">{label}</span>
              </button>
            ))}
          </div>
          <p className="mt-4 text-xs text-muted">System follows your device setting. Your choice is remembered on this device.</p>
        </Card>
        <Card eyebrow="Security" title="Change password">
          <div className="space-y-4">
            <Input label="Current password" type="password" autoComplete="current-password" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} />
            <div className="grid gap-4 sm:grid-cols-2">
              <Input label="New password" type="password" autoComplete="new-password" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} />
              <Input label="Confirm new password" type="password" autoComplete="new-password" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} />
            </div>
            {pwErr && <p role="alert" className="text-sm text-danger">{pwErr}</p>}
            <Button onClick={changePassword} loading={pwBusy} disabled={!pw.current || !pw.next}>Update password</Button>
          </div>
        </Card>
        <Card eyebrow="Your data" title="Export & deletion">
          <p className="text-sm text-muted">Download everything FinanceMate stores about you as JSON, or permanently delete your account and all associated records.</p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Button variant="secondary" onClick={() => download("/users/me/export", {}, "financemate-export.json").then(() => toast.success("Export downloaded")).catch((e) => toast.error(errMsg(e)))}><Download className="h-4 w-4" /> Export my data</Button>
            <Button variant="danger" onClick={() => setDel({ open: true, password: "", confirm: "", busy: false, err: "" })}><Trash2 className="h-4 w-4" /> Delete account</Button>
          </div>
        </Card>
      </div>
      <Modal open={del.open} onClose={() => setDel((d) => ({ ...d, open: false }))} title="Delete account permanently"
        footer={<><Button variant="secondary" onClick={() => setDel((d) => ({ ...d, open: false }))}>Cancel</Button><Button variant="danger" onClick={deleteAccount} loading={del.busy} disabled={del.confirm !== "DELETE" || !del.password}>Delete everything</Button></>}>
        <div className="space-y-4">
          <p className="text-sm">This removes your profile, transactions, budgets, goals, reports and conversations. It cannot be undone.</p>
          <Input label="Password" type="password" value={del.password} onChange={(e) => setDel({ ...del, password: e.target.value })} />
          <Input label='Type "DELETE" to confirm' value={del.confirm} onChange={(e) => setDel({ ...del, confirm: e.target.value })} />
          {del.err && <p role="alert" className="text-sm text-danger">{del.err}</p>}
        </div>
      </Modal>
    </>
  );
}
