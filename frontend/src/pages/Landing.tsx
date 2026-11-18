import { motion, useReducedMotion, useScroll, useTransform, type Variants } from "framer-motion";
import { ArrowRight, BarChart3, Feather, KeyRound, Lock, PiggyBank, ReceiptText, ShieldCheck, Upload, UserCheck, Wallet } from "lucide-react";
import { useRef, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Logo } from "../components/layout/Logo";
import { ThemeToggle } from "../components/layout/AppLayout";
import { JocastaAvatar } from "../components/jocasta/ChatView";
import { useAuth } from "../lib/auth";

const ease = [0.22, 1, 0.36, 1] as const;
const fadeUp: Variants = { hidden: { opacity: 0, y: 28 }, show: { opacity: 1, y: 0, transition: { duration: 0.9, ease } } };
const stagger: Variants = { hidden: {}, show: { transition: { staggerChildren: 0.12 } } };

function Reveal({ children, className, delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  return (
    <motion.div className={className} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }} variants={fadeUp} transition={{ delay }}>
      {children}
    </motion.div>
  );
}

function ImageReveal({ src, alt, className, imgClassName }: { src: string; alt: string; className?: string; imgClassName?: string }) {
  const reduce = useReducedMotion();
  return (
    <motion.div className={`relative overflow-hidden ${className ?? ""}`}
      initial={reduce ? false : { clipPath: "inset(12% 12% 12% 12% round 14px)", opacity: 0.4 }}
      whileInView={{ clipPath: "inset(0% 0% 0% 0% round 14px)", opacity: 1 }}
      viewport={{ once: true, margin: "-60px" }} transition={{ duration: 1.3, ease }}>
      <motion.img src={src} alt={alt} loading="lazy" className={`h-full w-full object-cover ${imgClassName ?? ""}`}
        initial={reduce ? false : { scale: 1.15 }} whileInView={{ scale: 1 }} viewport={{ once: true }} transition={{ duration: 1.8, ease }} />
    </motion.div>
  );
}

function Nav() {
  const { user } = useAuth();
  return (
    <motion.header initial={{ y: -30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.8, ease }}
      className="fixed inset-x-0 top-0 z-40 border-b border-line/50 bg-bg/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-8">
        <Logo />
        <nav className="hidden items-center gap-8 text-[13px] text-muted md:flex" aria-label="Landing">
          {[["Philosophy", "#philosophy"], ["Features", "#features"], ["JOCASTA", "#jocasta"], ["Security", "#security"]].map(([l, h]) => (
            <a key={h} href={h} className="relative transition hover:text-ink after:absolute after:-bottom-1 after:left-0 after:h-px after:w-0 after:bg-gold after:transition-all hover:after:w-full">{l}</a>
          ))}
        </nav>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          {user ? (
            <Link to="/app" className="whitespace-nowrap rounded-md bg-forest px-4 py-2 text-sm text-onforest transition hover:shadow-lift"><span className="hidden sm:inline">Open </span>Dashboard</Link>
          ) : (
            <>
              <Link to="/login" className="hidden text-sm text-ink hover:text-gold sm:block">Sign in</Link>
              <Link to="/register" className="whitespace-nowrap rounded-md bg-forest px-4 py-2 text-sm text-onforest transition hover:shadow-lift">Get started</Link>
            </>
          )}
        </div>
      </div>
    </motion.header>
  );
}

function Hero() {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });
  const y = useTransform(scrollYProgress, [0, 1], ["0%", reduce ? "0%" : "22%"]);
  const scale = useTransform(scrollYProgress, [0, 1], [1.05, reduce ? 1.05 : 1.18]);
  const textY = useTransform(scrollYProgress, [0, 1], ["0%", reduce ? "0%" : "40%"]);
  const fade = useTransform(scrollYProgress, [0, 0.7], [1, 0]);
  const words = "Your Wealth Deserves Intention.".split(" ");
  return (
    <section ref={ref} className="relative h-[100svh] min-h-[640px] overflow-hidden bg-[#1b211b]">
      <motion.img src="/images/hero-study.svg" alt="Open ledger, fountain pen and inkwell on a walnut desk in warm window light"
        style={{ y, scale }} className="absolute inset-0 h-full w-full object-cover" fetchPriority="high" />
      <div className="absolute inset-0 bg-gradient-to-r from-[#121812]/90 via-[#121812]/55 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-bg to-transparent" />
      <motion.div style={{ y: textY, opacity: fade }} className="relative z-10 mx-auto flex h-full max-w-7xl flex-col justify-center px-4 pt-16 sm:px-8">
        <motion.p initial={{ opacity: 0, letterSpacing: "0.5em" }} animate={{ opacity: 1, letterSpacing: "0.28em" }} transition={{ duration: 1.4, ease }}
          className="mb-6 text-[11px] uppercase text-[#C2A56E]">AI FinanceMate · Private ledger</motion.p>
        <h1 className="max-w-3xl font-serif text-[3.1rem] font-medium leading-[0.98] text-[#F4F0E6] sm:text-7xl lg:text-[5.6rem]">
          {words.map((w, i) => (
            <span key={i} className="inline-block overflow-hidden pb-2 align-bottom">
              <motion.span className={`inline-block ${w === "Intention." ? "italic text-[#D9BE85]" : ""}`}
                initial={{ y: "110%" }} animate={{ y: 0 }} transition={{ duration: 1.1, delay: 0.25 + i * 0.12, ease }}>
                {w}&nbsp;
              </motion.span>
            </span>
          ))}
        </h1>
        <motion.p initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 1, delay: 0.9, ease }}
          className="mt-6 max-w-xl text-lg leading-relaxed text-[#E9E1D2]/85">
          Understand your money. Make thoughtful decisions. Build a better financial future.
        </motion.p>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 1, delay: 1.1, ease }} className="mt-10 flex flex-wrap gap-4">
          <Link to="/register" className="group inline-flex h-12 items-center gap-2 rounded-md bg-[#C2A56E] px-7 text-[15px] font-medium text-[#1b1a12] shadow-lift transition hover:bg-[#D3B67D]">
            Enter FinanceMate <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" />
          </Link>
          <a href="#jocasta" className="inline-flex h-12 items-center gap-2 rounded-md border border-[#E9E1D2]/40 bg-[#121812]/55 px-7 text-[15px] text-[#F4F0E6] backdrop-blur-sm transition hover:border-[#C2A56E] hover:text-[#D9BE85]">
            Discover JOCASTA
          </a>
        </motion.div>
      </motion.div>
      <motion.div className="absolute bottom-10 left-1/2 z-10 hidden -translate-x-1/2 flex-col items-center gap-2 text-[10px] uppercase tracking-[0.3em] text-muted sm:flex"
        animate={reduce ? {} : { y: [0, 6, 0] }} transition={{ duration: 2.4, repeat: Infinity }}>
        Scroll <span className="h-8 w-px bg-gold/60" />
      </motion.div>
    </section>
  );
}

function Philosophy() {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });
  const y = useTransform(scrollYProgress, [0, 1], reduce ? ["0%", "0%"] : ["-8%", "8%"]);
  return (
    <section id="philosophy" ref={ref} className="relative overflow-hidden py-24 sm:py-36">
      <div className="mx-auto grid max-w-7xl items-center gap-14 px-4 sm:px-8 lg:grid-cols-12">
        <div className="lg:col-span-5">
          <div className="relative aspect-[4/5] overflow-hidden rounded-2xl shadow-lift">
            <motion.img style={{ y }} src="/images/facade.svg" alt="Neoclassical bank facade with columns at golden hour" loading="lazy" className="absolute inset-0 h-[116%] w-full object-cover" />
          </div>
        </div>
        <motion.div className="lg:col-span-6 lg:col-start-7" variants={stagger} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-100px" }}>
          <motion.p variants={fadeUp} className="eyebrow mb-5">I. Philosophy</motion.p>
          <motion.h2 variants={fadeUp} className="font-serif text-4xl font-medium leading-tight sm:text-6xl">Financial Clarity, <em className="text-gold">Without the Complexity.</em></motion.h2>
          <motion.div variants={fadeUp} className="gold-rule my-8 w-40" />
          <motion.p variants={fadeUp} className="text-lg leading-relaxed text-muted">
            Old institutions earned trust through patience, precision and discretion. FinanceMate brings that temperament to your personal ledger:
            every figure is calculated from the records you keep, every recommendation shows its reasoning, and nothing changes without your consent.
          </motion.p>
          <motion.div variants={fadeUp} className="mt-10 grid grid-cols-3 gap-6 border-t border-line pt-8">
            {[["Exact", "Decimal arithmetic for every rupee"], ["Explained", "Recommendations show their basis"], ["Yours", "Data isolated to your account"]].map(([k, v]) => (
              <div key={k}><p className="font-serif text-2xl text-ink">{k}</p><p className="mt-1 text-xs leading-relaxed text-muted">{v}</p></div>
            ))}
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}

const FEATURES = [
  { icon: ReceiptText, title: "Intelligent expense tracking", text: "Record transactions by hand, import CSV, Excel or text-based PDF statements, and let rule-based categorisation — with visible confidence — do the filing." },
  { icon: Wallet, title: "Smart budgeting", text: "Budgets per category with live utilisation. Recommendations come from your spending history, weighted averages and trend analysis — and are saved only when you approve." },
  { icon: BarChart3, title: "Financial insights", text: "Income versus expenditure, month-over-month movements, daily trends and category breakdowns, drawn precisely from your records." },
  { icon: PiggyBank, title: "Savings goals", text: "Set a target and a date. FinanceMate calculates what remains and the monthly contribution required to arrive on time." },
  { icon: Feather, title: "JOCASTA AI assistant", text: "Ask in plain language. JOCASTA records, edits and analyses on your behalf — and always asks before changing anything." },
];

function Features() {
  return (
    <section id="features" className="bg-bg2/60 py-24 sm:py-36">
      <div className="mx-auto max-w-7xl px-4 sm:px-8">
        <Reveal className="mx-auto max-w-2xl text-center">
          <p className="eyebrow mb-5">II. The Instruments</p>
          <h2 className="font-serif text-4xl font-medium leading-tight sm:text-6xl">Everything a careful steward needs.</h2>
        </Reveal>
        <div className="mt-20 grid items-center gap-14 lg:grid-cols-2">
          <ImageReveal src="/images/desk-flatlay.svg" alt="Walnut desk with leather budget notebook, brass compass, receipt and coins" className="aspect-[4/3] rounded-2xl shadow-lift" />
          <motion.ul variants={stagger} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }} className="divide-y divide-line">
            {FEATURES.map(({ icon: Icon, title, text }, i) => (
              <motion.li key={title} variants={fadeUp} className="group flex gap-5 py-6">
                <span className="font-serif text-sm italic text-gold">{String(i + 1).padStart(2, "0")}</span>
                <div>
                  <h3 className="flex items-center gap-2.5 font-serif text-2xl text-ink"><Icon className="h-5 w-5 text-gold transition group-hover:rotate-[-8deg]" strokeWidth={1.5} />{title}</h3>
                  <p className="mt-2 text-[15px] leading-relaxed text-muted">{text}</p>
                </div>
              </motion.li>
            ))}
          </motion.ul>
        </div>
      </div>
    </section>
  );
}

function ChatPreview() {
  const lines = [
    { me: true, t: "Add ₹500 for groceries today." },
    { me: false, t: "I've prepared a new transaction. Should I add it?", card: true },
    { me: true, t: "Yes." },
    { me: false, t: "Done. Your ₹500 grocery transaction has been added." },
  ];
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center gap-3 bg-forest px-5 py-3.5 text-onforest dark:bg-[#1c261f]">
        <JocastaAvatar size={34} />
        <div><p className="font-serif text-lg leading-none tracking-[0.12em]">JOCASTA</p><p className="mt-1 text-[10px] uppercase tracking-[0.2em] text-[#C2A56E]">Online</p></div>
      </div>
      <motion.div className="space-y-3 p-5" variants={{ show: { transition: { staggerChildren: 0.45 } } }} initial="hidden" whileInView="show" viewport={{ once: true }}>
        {lines.map((l, i) => (
          <motion.div key={i} variants={fadeUp} className={`flex ${l.me ? "justify-end" : ""}`}>
            <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${l.me ? "rounded-tr-sm bg-forest text-onforest" : "rounded-tl-sm border border-line bg-bg text-ink"}`}>
              {l.t}
              {l.card && (
                <div className="mt-2.5 rounded-lg border border-gold/50 bg-card p-3 text-[12.5px]">
                  {[["Category", "Food & Groceries"], ["Amount", "₹500"], ["Date", "Today"]].map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-6 py-0.5"><span className="text-muted">{k}</span><span className="font-medium">{v}</span></div>
                  ))}
                  <div className="mt-2 flex gap-2"><span className="rounded bg-forest px-2.5 py-1 text-[11px] text-onforest">Confirm</span><span className="rounded border border-line px-2.5 py-1 text-[11px]">Cancel</span></div>
                </div>
              )}
            </div>
          </motion.div>
        ))}
      </motion.div>
    </div>
  );
}

function Jocasta() {
  return (
    <section id="jocasta" className="relative overflow-hidden py-24 sm:py-36">
      <div className="mx-auto grid max-w-7xl items-center gap-16 px-4 sm:px-8 lg:grid-cols-2">
        <div>
          <Reveal><p className="eyebrow mb-5">III. Your Assistant</p></Reveal>
          <Reveal><h2 className="font-serif text-4xl font-medium leading-tight sm:text-6xl">Meet <span className="tracking-[0.08em]">JOCASTA</span>.</h2></Reveal>
          <Reveal><p className="mt-6 text-lg leading-relaxed text-muted">A calm, capable assistant who keeps your books in order. JOCASTA works through a team of specialised agents — transactions, categorisation, analysis, budgets and savings — and draws every figure from your actual records.</p></Reveal>
          <Reveal className="mt-8 grid gap-3 sm:grid-cols-2">
            {["“Show my last five expenses.”", "“Increase my shopping budget to ₹3,000.”", "“Compare this month with last month.”", "“How much more do I need to save?”"].map((q) => (
              <p key={q} className="rounded-lg border border-line bg-card px-4 py-3 font-serif text-lg italic text-ink">{q}</p>
            ))}
          </Reveal>
          <Reveal className="mt-8"><p className="text-sm text-muted">Changes are proposed first, shown on a confirmation card, and carried out only after you approve.</p></Reveal>
        </div>
        <div className="relative">
          <ImageReveal src="/images/correspondence.svg" alt="A letter signed by Jocasta with a gold wax seal on green leather" className="absolute -right-6 -top-10 hidden aspect-[4/3] w-3/4 rounded-2xl opacity-90 shadow-lift lg:block" />
          <div className="relative lg:mr-24 lg:mt-36"><ChatPreview /></div>
        </div>
      </div>
    </section>
  );
}

function HowItWorks() {
  const steps = [
    { icon: Upload, t: "Bring your financial records.", d: "Add transactions as you go or import a bank statement. Preview everything before it is saved; duplicates are flagged." },
    { icon: BarChart3, t: "Understand your financial patterns.", d: "See where money goes, how this month compares with the last, and which budgets are under pressure." },
    { icon: PiggyBank, t: "Plan your next financial goals.", d: "Approve data-driven budgets and set savings goals with a clear monthly path to reach them." },
  ];
  return (
    <section className="border-y border-line bg-card py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-4 sm:px-8">
        <Reveal className="mb-16 text-center"><p className="eyebrow mb-5">IV. The Method</p><h2 className="font-serif text-4xl font-medium sm:text-5xl">Three deliberate steps.</h2></Reveal>
        <motion.ol variants={stagger} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }} className="grid gap-10 md:grid-cols-3">
          {steps.map(({ icon: Icon, t, d }, i) => (
            <motion.li key={t} variants={fadeUp} className="relative text-center">
              <div className="mx-auto mb-6 grid h-20 w-20 place-items-center rounded-full border border-gold/50 bg-bg">
                <Icon className="h-7 w-7 text-gold" strokeWidth={1.4} />
              </div>
              <p className="font-serif text-sm italic text-gold">Step {["one", "two", "three"][i]}</p>
              <h3 className="mt-2 font-serif text-2xl text-ink">{t}</h3>
              <p className="mx-auto mt-3 max-w-xs text-[15px] leading-relaxed text-muted">{d}</p>
              {i < 2 && <span className="absolute right-[-12%] top-10 hidden h-px w-1/4 bg-gradient-to-r from-gold/60 to-transparent md:block" aria-hidden />}
            </motion.li>
          ))}
        </motion.ol>
      </div>
    </section>
  );
}

function Security() {
  const items = [
    { icon: UserCheck, t: "Strict data isolation", d: "Every query is scoped to your account on the server. JOCASTA's tools receive your identity from the session — never from the AI." },
    { icon: KeyRound, t: "Secure authentication", d: "Passwords are hashed with Argon2id. Sessions use short-lived signed tokens; signing out or changing your password revokes them." },
    { icon: Lock, t: "Documents not retained", d: "Uploaded statements are parsed in a temporary file and deleted immediately. Only the transactions you approve are stored." },
    { icon: ShieldCheck, t: "Consent before change", d: "The assistant cannot run arbitrary database commands. Edits and deletions require your explicit confirmation and are audit-logged." },
  ];
  return (
    <section id="security" className="py-24 sm:py-36">
      <div className="mx-auto max-w-7xl px-4 sm:px-8">
        <div className="grid gap-14 lg:grid-cols-12">
          <Reveal className="lg:col-span-4">
            <p className="eyebrow mb-5">V. Discretion</p>
            <h2 className="font-serif text-4xl font-medium leading-tight sm:text-5xl">Security and privacy, by design.</h2>
            <p className="mt-5 text-[15px] leading-relaxed text-muted">FinanceMate never asks for banking passwords, OTPs or card numbers, and does not move money. You can export or permanently delete your data at any time from Settings.</p>
          </Reveal>
          <motion.div variants={stagger} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }} className="grid gap-5 sm:grid-cols-2 lg:col-span-8">
            {items.map(({ icon: Icon, t, d }) => (
              <motion.div key={t} variants={fadeUp} whileHover={{ y: -4 }} className="card p-6 transition-shadow hover:shadow-lift">
                <Icon className="h-6 w-6 text-gold" strokeWidth={1.4} />
                <h3 className="mt-4 font-serif text-xl text-ink">{t}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted">{d}</p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </div>
    </section>
  );
}

function FinalCta() {
  return (
    <section className="relative overflow-hidden bg-[#1F3026] py-28 text-center sm:py-40 dark:bg-[#111713]">
      <div className="absolute inset-0 opacity-[.07]" style={{ backgroundImage: "repeating-linear-gradient(45deg, #C2A56E 0 1px, transparent 1px 22px)" }} aria-hidden />
      <Reveal className="relative mx-auto max-w-3xl px-4">
        <p className="mb-6 text-[11px] uppercase tracking-[0.3em] text-[#C2A56E]">VI. Begin</p>
        <h2 className="font-serif text-5xl font-medium leading-tight text-[#F4F0E6] sm:text-7xl">Take Control of Your <em className="text-[#D9BE85]">Financial Story.</em></h2>
        <Link to="/register" className="group mt-12 inline-flex h-12 items-center gap-2 rounded-md bg-[#C2A56E] px-8 text-[15px] font-medium text-[#1b1a12] shadow-lift transition hover:bg-[#D3B67D]">
          Get Started <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" />
        </Link>
        <p className="mt-5 text-xs text-[#E9E1D2]/60">Free to use. No bank credentials required.</p>
      </Reveal>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-line bg-bg py-14">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 sm:px-8 md:grid-cols-4">
        <div className="md:col-span-2">
          <Logo />
          <p className="mt-4 max-w-sm text-sm text-muted">AI FinanceMate is a personal finance management and budget planning platform. It is an educational and organisational tool and does not provide investment advice or process payments.</p>
        </div>
        <div>
          <p className="eyebrow mb-4">Navigate</p>
          <ul className="space-y-2 text-sm text-muted">
            <li><a href="#philosophy" className="hover:text-ink">Philosophy</a></li><li><a href="#features" className="hover:text-ink">Features</a></li>
            <li><a href="#jocasta" className="hover:text-ink">JOCASTA</a></li><li><Link to="/login" className="hover:text-ink">Sign in</Link></li>
          </ul>
        </div>
        <div>
          <p className="eyebrow mb-4">Information</p>
          <ul className="space-y-2 text-sm text-muted">
            <li><Link to="/privacy" className="hover:text-ink">Privacy</Link></li><li><Link to="/terms" className="hover:text-ink">Terms</Link></li>
            {import.meta.env.VITE_CONTACT_EMAIL && <li><a href={`mailto:${import.meta.env.VITE_CONTACT_EMAIL}`} className="hover:text-ink">Contact</a></li>}
          </ul>
        </div>
      </div>
      <div className="mx-auto mt-12 flex max-w-7xl flex-col justify-between gap-2 border-t border-line px-4 pt-6 text-xs text-muted sm:flex-row sm:px-8">
        <p>© {new Date().getFullYear()} AI FinanceMate. Crafted with intention.</p>
        <p>Illustrations are original artwork created for this project.</p>
      </div>
    </footer>
  );
}

export default function Landing() {
  return (
    <div className="bg-bg">
      <Nav />
      <main>
        <Hero />
        <Philosophy />
        <Features />
        <Jocasta />
        <HowItWorks />
        <Security />
        <FinalCta />
      </main>
      <Footer />
    </div>
  );
}
