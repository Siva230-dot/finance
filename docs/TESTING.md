# Testing

## Backend — Pytest (65 tests)
```bash
cd backend && source .venv/bin/activate
pytest                    # uses TEST_DATABASE_URL (schema is dropped & migrated fresh)
pytest --cov=app          # ~85% line coverage
```
| File | Covers |
|---|---|
| `test_auth.py` | registration, login, wrong password, duplicates, weak passwords, token required, logout revocation, profile/currency, password change, export, account deletion, health |
| `test_transactions.py` | CRUD, auto-categorisation, soft delete + audit, validation (negative/zero/3-decimals/bad type/date), filters/search/sort, CSV export, duplicates, recurring, custom categories |
| `test_isolation.py` | cross-user read/update/delete attempts on transactions, budgets, goals, categories, analytics |
| `test_budgets_savings.py` | budget CRUD, utilisation/status, uniqueness, recommendations requiring approval, goal lifecycle & maths, reports (JSON/PDF/CSV), Decimal accuracy (0.1+0.2) |
| `test_calculations.py` | money helpers, laptop goal example (₹40,000 over 8 months → ₹5,000), deterministic recommendations, rule categorisation |
| `test_uploads.py` | CSV with preamble & duplicates, approval with overrides, reject, isolation, XLSX, text PDF, scanned PDF message, file validation (type, MIME, magic bytes, size, format) |
| `test_agents.py` | intent classification (10 phrasings), LLM fallback, create → confirm via "yes", success-claim guard, list → update → confirm, delete → cancel, cross-user tool attack, tool allowlists, summary accuracy, recommendation tool, savings via assistant, Groq rate-limit failure, iteration limit, unconfigured LLM, per-user history |
| `test_tools_direct.py` | every tool executed through ToolContext and confirmed; no `user_id` tool args; expired confirmations |

The LLM is replaced by a scripted fake (`tests/conftest.py::ScriptedLLM`) so agent tests are deterministic and need no API key.

## Frontend — Vitest + Testing Library (12 tests)
```bash
cd frontend
npm test
npx tsc -b && npm run build
```
Covers formatting, theme switching & persistence, protected-route redirect, login validation/success/error, registration rules, transaction form (decimal string amounts), budget status + recommendation approval, savings goal list/validation/create, JOCASTA send → confirmation card → confirm → result, assistant error state, error/retry state.

## Manual checks performed
Landing page animations and imagery; login with the demo account; Overview, Transactions, Budgets (recommendation generation), Savings and the JOCASTA panel in light and dark themes; 375 px mobile layout with no horizontal overflow; production gunicorn boot with docs disabled and CORS allowlist.

## CI
`.github/workflows/ci.yml` runs both suites on push/PR with a PostgreSQL service.
