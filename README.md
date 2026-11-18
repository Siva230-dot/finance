# AI FinanceMate

AI-powered personal finance management and smart budget planning, with **JOCASTA** — a multi-agent finance assistant that performs real application operations through natural language, always asking before it changes your records.

Old-money visual language (Cormorant Garamond, forest green, antique gold, parchment) in fully themed light and dark modes.

| Layer | Stack |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, Framer Motion, Recharts, React Router, TanStack Query, React Hook Form, Zod |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Pydantic 2, Alembic, PostgreSQL, JWT (python-jose), Argon2id |
| Agents | LangChain tools, LangGraph supervisor graph, `langchain-groq` (Groq `openai/gpt-oss-120b` by default) |
| Analysis | Decimal/NUMERIC money maths, scikit-learn trend regression, pandas, pdfplumber + PyMuPDF, ReportLab |

No MCP is used anywhere. The browser never talks to Groq; every LLM call goes through FastAPI.

## Quick start (local)

```bash
# 1. Backend
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # then fill DATABASE_URL, JWT_SECRET_KEY, GROQ_API_KEY
createdb financemate && createdb financemate_test
alembic upgrade head
python -m app.scripts.seed_demo # optional synthetic demo data
uvicorn app.main:app --reload   # http://localhost:8000/api/docs

# 2. Frontend (new terminal)
cd frontend
cp .env.example .env            # VITE_API_BASE_URL=http://localhost:8000/api/v1
npm install
npm run dev                     # http://localhost:5173
```

Demo account (synthetic data only): see `backend/app/scripts/seed_demo.py`.

## Tests

```bash
cd backend && pytest            # 65 tests: auth, CRUD, isolation, uploads, calculations, agents
cd frontend && npm test         # 12 tests: auth, navigation, theme, CRUD forms, JOCASTA, states
```

## Project structure

```
backend/
  app/
    agents/        LangGraph graph, LangChain tools, confirmation actions, Groq provider
    api/routes/    /auth /users /categories /transactions /budgets /savings /analytics /reports /uploads /assistant /health
    core/          settings, database, security, errors, rate limiting
    models/        SQLAlchemy models (13 tables)
    schemas/       Pydantic request/response models
    services/      domain logic shared by REST and agent tools
    scripts/       synthetic demo seed
  alembic/         migrations (0001 initial schema + category seed)
  tests/
frontend/
  public/images/   original SVG artwork (landing page)
  src/
    components/    ui kit, layout, charts, jocasta (chat, cards, launcher)
    lib/           api client, auth, theme, queries, formatting
    pages/         Landing, Auth, Overview, Transactions, Budgets, Savings, Analytics, Reports, JOCASTA, Settings
    test/
docs/              requirements, architecture, schema, API, agents, security, setup, deployment, testing
render.yaml        Render free web service blueprint
frontend/vercel.json
```

## Documentation

- [Project overview](docs/PROJECT_OVERVIEW.md)
- [Software requirements](docs/SOFTWARE_REQUIREMENTS.md)
- [System architecture](docs/SYSTEM_ARCHITECTURE.md)
- [Database schema](docs/DATABASE_SCHEMA.md)
- [API documentation](docs/API_DOCUMENTATION.md)
- [Agent workflows](docs/AGENT_WORKFLOWS.md)
- [Security](docs/SECURITY.md)
- [Local setup](docs/LOCAL_SETUP.md)
- [Deployment (free tiers)](docs/DEPLOYMENT.md)
- [Testing](docs/TESTING.md)

## Status

See [docs/PROJECT_OVERVIEW.md § Implementation status](docs/PROJECT_OVERVIEW.md#implementation-status) for an honest list of what is verified and what still needs your action (Groq key, live deployment).
