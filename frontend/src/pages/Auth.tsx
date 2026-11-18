import { zodResolver } from "@hookform/resolvers/zod";
import { motion } from "framer-motion";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";
import { Logo } from "../components/layout/Logo";
import { ThemeToggle } from "../components/layout/AppLayout";
import { Button, Input, Select } from "../components/ui";
import { useAuth } from "../lib/auth";

const loginSchema = z.object({ email: z.string().email("Enter a valid email"), password: z.string().min(1, "Password is required") });
const registerSchema = z.object({
  full_name: z.string().trim().min(1, "Your name is required").max(120),
  email: z.string().email("Enter a valid email"),
  password: z.string().min(8, "At least 8 characters").regex(/[A-Za-z]/, "Include a letter").regex(/\d/, "Include a number"),
  confirm: z.string(),
  currency: z.string().length(3),
}).refine((d) => d.password === d.confirm, { path: ["confirm"], message: "Passwords do not match" });

function Shell({ title, subtitle, children, footer }: { title: string; subtitle: string; children: React.ReactNode; footer: React.ReactNode }) {
  return (
    <div className="grid min-h-screen bg-bg lg:grid-cols-2">
      <div className="relative hidden overflow-hidden lg:block">
        <motion.img src="/images/hero-study.svg" alt="" className="absolute inset-0 h-full w-full object-cover" initial={{ scale: 1.12 }} animate={{ scale: 1 }} transition={{ duration: 2.4, ease: [0.22, 1, 0.36, 1] }} />
        <div className="absolute inset-0 bg-gradient-to-t from-[#121812]/90 via-[#121812]/30 to-transparent" />
        <div className="absolute bottom-12 left-12 right-12">
          <p className="font-serif text-4xl italic leading-snug text-[#F4F0E6]">“Beware of little expenses; a small leak will sink a great ship.”</p>
          <p className="mt-3 text-xs uppercase tracking-[0.25em] text-[#C2A56E]">Benjamin Franklin</p>
        </div>
      </div>
      <div className="flex flex-col px-6 py-8 sm:px-12">
        <div className="flex items-center justify-between"><Logo /><ThemeToggle /></div>
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="mx-auto my-auto w-full max-w-md py-10">
          <h1 className="font-serif text-4xl font-semibold">{title}</h1>
          <p className="mt-2 text-sm text-muted">{subtitle}</p>
          <div className="gold-rule my-7" />
          {children}
          <p className="mt-8 text-center text-sm text-muted">{footer}</p>
        </motion.div>
      </div>
    </div>
  );
}

export function Login() {
  const { login, user } = useAuth();
  const nav = useNavigate();
  const loc = useLocation() as { state?: { from?: string } };
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<z.infer<typeof loginSchema>>({ resolver: zodResolver(loginSchema) });
  if (user) return <Navigate to="/app" replace />;
  const onSubmit = handleSubmit(async (v) => {
    setError(null);
    try { await login(v.email, v.password); nav(loc.state?.from || "/app", { replace: true }); }
    catch (e) { setError((e as Error).message); }
  });
  return (
    <Shell title="Welcome back" subtitle="Sign in to your FinanceMate ledger." footer={<>New here? <Link to="/register" className="text-gold hover:underline">Create an account</Link></>}>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Input label="Email" type="email" autoComplete="email" {...register("email")} error={errors.email?.message} />
        <Input label="Password" type="password" autoComplete="current-password" {...register("password")} error={errors.password?.message} />
        {error && <p role="alert" className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">{error}</p>}
        <Button type="submit" className="w-full" size="lg" loading={isSubmitting}>Sign in</Button>
      </form>
    </Shell>
  );
}

export function Register() {
  const { register: signUp, user } = useAuth();
  const nav = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<z.infer<typeof registerSchema>>({ resolver: zodResolver(registerSchema), defaultValues: { currency: "INR" } });
  if (user) return <Navigate to="/app" replace />;
  const onSubmit = handleSubmit(async (v) => {
    setError(null);
    try { await signUp({ email: v.email, full_name: v.full_name, password: v.password, currency: v.currency }); nav("/app", { replace: true }); }
    catch (e) { setError((e as Error).message); }
  });
  return (
    <Shell title="Open your ledger" subtitle="Create a private FinanceMate account in under a minute." footer={<>Already have an account? <Link to="/login" className="text-gold hover:underline">Sign in</Link></>}>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Input label="Full name" autoComplete="name" {...register("full_name")} error={errors.full_name?.message} />
        <Input label="Email" type="email" autoComplete="email" {...register("email")} error={errors.email?.message} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Password" type="password" autoComplete="new-password" {...register("password")} error={errors.password?.message} />
          <Input label="Confirm password" type="password" autoComplete="new-password" {...register("confirm")} error={errors.confirm?.message} />
        </div>
        <Select label="Currency" {...register("currency")}>
          {["INR", "USD", "EUR", "GBP", "JPY", "AUD", "CAD", "SGD", "AED", "CHF"].map((c) => <option key={c}>{c}</option>)}
        </Select>
        {error && <p role="alert" className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">{error}</p>}
        <Button type="submit" className="w-full" size="lg" loading={isSubmitting}>Create account</Button>
        <p className="text-center text-[11px] text-muted">We never ask for bank passwords, OTPs or card numbers.</p>
      </form>
    </Shell>
  );
}
