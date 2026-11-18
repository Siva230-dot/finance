# Local Setup

Prerequisites: Python 3.12, Node 20+ (tested on 24), PostgreSQL 14+ (tested on 18).

## Backend
```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

### `backend/.env` variables
| Variable | Required | Example / notes |
|---|---|---|
| `APP_ENV` | yes | `development` (or `production`, `test`) |
| `APP_NAME` | no | `AI_FinanceMate` |
| `GROQ_API_KEY` | for JOCASTA | Create at https://console.groq.com/keys. Never commit it |
| `GROQ_MODEL` | yes | `openai/gpt-oss-120b` (active on Groq, Nov 2026). `openai/gpt-oss-20b` is a faster alternative |
| `GROQ_TIMEOUT_SECONDS`, `GROQ_MAX_RETRIES` | no | `30`, `2` |
| `DATABASE_URL` | yes | `postgresql+psycopg://postgres@localhost:5432/financemate` (`postgres://` URLs are normalised automatically) |
| `TEST_DATABASE_URL` | tests | `postgresql+psycopg://postgres@localhost:5432/financemate_test` — **dropped and recreated by the test suite** |
| `JWT_SECRET_KEY` | yes | `python -c "import secrets;print(secrets.token_urlsafe(48))"` |
| `JWT_ALGORITHM` | no | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `30` |
| `FRONTEND_URL` | yes | `http://localhost:5173` |
| `CORS_ORIGINS` | yes | comma-separated, e.g. `http://localhost:5173` |
| `MAX_UPLOAD_SIZE_MB` | no | `10` |
| `RATE_LIMIT_DEFAULT` | no | `120/minute` |
| `LOG_LEVEL` | no | `INFO` |

```bash
createdb financemate
createdb financemate_test
alembic upgrade head
python -m app.scripts.seed_demo      # optional synthetic data (--reset to recreate)
uvicorn app.main:app --reload        # API on :8000, docs at /api/docs
```

## Frontend
```bash
cd frontend
cp .env.example .env                 # VITE_API_BASE_URL=http://localhost:8000/api/v1
npm install
npm run dev                          # http://localhost:5173
```
`frontend/.env` holds **public** values only (`VITE_API_BASE_URL`, optional `VITE_CONTACT_EMAIL`). Anything prefixed `VITE_` ships to the browser.

If port 5173 is taken, run `npm run dev -- --port 5180` and add that origin to `CORS_ORIGINS`.
