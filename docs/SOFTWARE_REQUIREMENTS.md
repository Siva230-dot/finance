# Software Requirements Specification

## 1. Purpose
Provide a secure, intelligent personal finance platform with an AI assistant (JOCASTA) able to perform real CRUD operations under user confirmation.

## 2. Users
Students, working professionals, individuals tracking monthly expenses, people planning savings.

## 3. Functional requirements

| ID | Requirement | Implemented in |
|---|---|---|
| FR-1 | Register, login, logout, profile, currency, password change | `api/routes/auth.py`, `users.py` |
| FR-2 | Each user accesses only their own records | every service query filters `user_id`; `tests/test_isolation.py` |
| FR-3 | Transaction CRUD with search, filters, sorting, CSV export | `services/transactions.py`, `routes/transactions.py` |
| FR-4 | Duplicate detection (hash of date, amount, type, normalised description) | `dedupe_hash`, `/transactions/duplicates`, upload preview |
| FR-5 | Recurring transactions | `is_recurring`, `/transactions/recurring/run` |
| FR-6 | Statement upload CSV/XLSX/PDF with preview & approval; temp files deleted | `services/statements.py`, `routes/uploads.py` |
| FR-7 | Automatic categorisation with confidence, LLM assist, user correction, custom categories | `services/categories.py` |
| FR-8 | Analytics from stored data only | `services/analytics.py` |
| FR-9 | Budgets, utilisation, overspending, recommendations needing approval | `services/budgets.py` |
| FR-10 | Savings goals and contributions with deterministic required-monthly maths | `services/savings.py` |
| FR-11 | Monthly/annual reports, PDF and CSV | `services/reports.py` |
| FR-12 | JOCASTA with 18 typed tools, supervisor routing, confirmations, cancellation | `app/agents/*` |
| FR-13 | Landing page, light/dark themes, responsive dashboard | `frontend/src` |

## 4. Non-functional requirements
- **Money accuracy**: `NUMERIC(14,2)` columns, Python `Decimal`, decimal strings in JSON. No float maths on money.
- **Security**: Argon2id, JWT expiry (30 min default), CORS allowlist, rate limiting, validation, audit log, no secrets in code.
- **Privacy**: original documents never stored; export & delete account.
- **Availability on free tiers**: DB `pool_pre_ping`, 503 envelope when DB unavailable, frontend retries and "server waking up" messages.
- **Accessibility**: semantic landmarks, labelled controls, focus rings, keyboard-closable dialogs, `prefers-reduced-motion` honoured.
- **Performance**: route-level code splitting; vendor chunks for charts/motion.

## 5. Constraints
Groq is the only LLM provider; no MCP; free hosting only (Vercel Hobby, Render Free, Supabase Free).
