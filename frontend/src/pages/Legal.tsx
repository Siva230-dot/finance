import { Link } from "react-router-dom";
import { Logo } from "../components/layout/Logo";

const CONTENT = {
  privacy: {
    title: "Privacy",
    body: [
      "FinanceMate stores the account details you provide (name, email, currency preference) and the financial records you enter or approve for import: transactions, budgets, savings goals, reports and assistant conversations.",
      "Uploaded bank statements are processed in a temporary file on the server and deleted as soon as parsing completes. The original document is not stored; extracted rows are kept only until you approve or reject the import.",
      "When you use JOCASTA, your message and the relevant figures fetched from your records are sent to the Groq API to generate a response. Your password is never sent.",
      "Every record is scoped to your account. You can export all of your data or permanently delete your account from Settings.",
      "FinanceMate does not sell data, does not collect banking passwords, OTPs or card numbers, and does not initiate payments.",
    ],
  },
  terms: {
    title: "Terms",
    body: [
      "FinanceMate is provided as-is for personal budgeting and record keeping. It does not provide licensed financial, investment, tax or legal advice.",
      "Automatic categories and AI explanations can be wrong. Review imported transactions and recommendations before relying on them.",
      "Do not upload other people's financial data or use public demo accounts for real financial information.",
      "Free hosting tiers may sleep or have usage limits; availability is not guaranteed.",
    ],
  },
};

export default function Legal({ kind }: { kind: "privacy" | "terms" }) {
  const c = CONTENT[kind];
  return (
    <div className="min-h-screen bg-bg px-4 py-10 sm:px-8">
      <div className="mx-auto max-w-2xl">
        <Logo />
        <h1 className="mt-12 font-serif text-5xl">{c.title}</h1>
        <div className="gold-rule my-8" />
        <div className="space-y-5 text-[15px] leading-relaxed text-ink/90">{c.body.map((p, i) => <p key={i}>{p}</p>)}</div>
        <Link to="/" className="mt-10 inline-block text-sm text-gold hover:underline">← Back to home</Link>
      </div>
    </div>
  );
}
