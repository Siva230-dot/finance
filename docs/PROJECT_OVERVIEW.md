# Project Overview

**AI FinanceMate** helps students, working professionals and households manage money with intention: record and import transactions, plan budgets from real history, track savings goals, read clear analytics, download reports, and delegate routine work to **JOCASTA**, an AI assistant built on a LangGraph multi-agent system.

Default currency is INR (₹); users can choose INR, USD, EUR, GBP, JPY, AUD, CAD, SGD, AED or CHF. Changing currency changes display only — amounts are not converted.

Out of scope for the MVP: stock/crypto trading, payments, bank-account connections, OCR of scanned statements.

## Modules

| Module | Highlights |
|---|---|
| A. Authentication | Register, login, logout (token revocation), profile, currency, theme preference, password change, data export, account deletion |
| B. Transactions | CRUD, search (description, notes, category), category/type/date filters, sorting, pagination, CSV export, duplicate detection, recurring entries (weekly/monthly/yearly), soft delete |
| C. Statement import | CSV, XLSX, text-based PDF → validate → extract → normalise → categorise → flag duplicates → preview → approve/reject → save. Temp files deleted immediately |
| D. Categorisation | 14 system categories + custom categories; ordered keyword rules with confidence; optional LLM assistance (capped confidence, validated output); user corrections set confidence to 100% |
| E. Analytics | Monthly income/expense/savings, savings rate, category breakdown, average monthly spend, top categories, month-over-month, daily trend, income vs expenditure, budget utilisation |
| F. Budget planner | Category budgets per month, utilisation & status, copy previous month, deterministic recommendations (weighted average + scikit-learn trend) with basis, reason, expected effect, confidence and limitations; saved only on approval |
| G. Savings goals | CRUD, contributions/withdrawals, remaining amount, progress, months remaining, required monthly contribution (rounded up) |
| H. Reports | Monthly and annual reports from stored records; on-screen, PDF (ReportLab) and CSV; generation history |
| JOCASTA | Floating panel + full page, history, typing indicator, tool status chips, confirmation cards, result cards, suggestion chips, error states |

## Implementation status

Verified locally (automated tests + manual browser checks):

- Backend: 65 pytest tests pass against PostgreSQL (auth, CRUD, isolation, uploads, maths, agents, confirmations, Groq failure handling).
- Frontend: 12 Vitest tests pass; `tsc` clean; production build succeeds; pages checked in the browser in light/dark themes and at 375 px and 1360 px widths.
- Production configuration smoke-tested with gunicorn (`APP_ENV=production`): OpenAPI docs hidden, CORS allowlist enforced, HSTS header present.

Requires your action:

- **Groq**: no `GROQ_API_KEY` was available during development, so JOCASTA's live LLM path has not been exercised against Groq. The graph, tools, routing, confirmation flow and error handling are tested with a scripted model. Add your key to `backend/.env` and try the prompts in [AGENT_WORKFLOWS.md](AGENT_WORKFLOWS.md#manual-verification).
- **Deployment**: needs your Vercel, Render and Supabase accounts. Configuration is ready; follow [DEPLOYMENT.md](DEPLOYMENT.md). Nothing has been deployed yet.

Known limitations:

- Scanned (image-only) PDFs are rejected with a clear message; no OCR.
- PDF statement layouts vary widely; table extraction plus a line-pattern fallback cover common text PDFs, but review the preview.
- Logout revokes *all* of a user's tokens (token-version scheme), i.e. it signs out every device.
- Rate limits are in-memory per instance (fine for a single free Render instance).
- Landing-page imagery is original SVG artwork made for the project rather than photography.
