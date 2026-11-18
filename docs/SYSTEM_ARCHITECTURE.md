# System Architecture

```
 Browser (React SPA on Vercel)
   │  HTTPS, Authorization: Bearer <JWT>
   ▼
 FastAPI (Render Free web service)  /api/v1/*
   ├── Auth & deps ── JWT decode → User (token_version checked)
   ├── REST routes ── services/* (all queries scoped by user_id)
   ├── /assistant ─── agents/service.py
   │                    ├─ yes/no reply to pending confirmation → actions.confirm/cancel (deterministic)
   │                    └─ LangGraph: supervisor → specialist agent ⇄ tools → finalize
   │                          tools = closures over ToolContext(db, authenticated user)
   │                          LLM = ChatGroq (server-side key)
   └── SQLAlchemy ─────► PostgreSQL (Supabase Free)
```

## Backend layers
- **core/** – `config.py` (Pydantic Settings, env only), `database.py` (engine with `pool_pre_ping`), `security.py` (Argon2id, JWT), `deps.py` (current user), `errors.py` (uniform envelope `{"error":{code,message,details}}`), `rate_limit.py` (slowapi).
- **services/** – pure domain logic shared by REST routes and agent tools, so the assistant can never do something the API cannot.
- **agents/** – `tools.py` (18 StructuredTools + `suggest_category`), `graph.py` (LangGraph), `actions.py` (confirmed execution), `service.py` (conversation persistence), `llm.py` (Groq provider, swappable in tests).
- **api/routes/** – thin HTTP layer with Pydantic schemas.

## Frontend layers
- **lib/** – `api.ts` (fetch wrapper, timeout, error envelope, 401 handling), `auth.tsx`, `theme.tsx` (system/light/dark, persisted; pre-paint script in `index.html` prevents flash), `queries.ts` (TanStack Query hooks; every mutation invalidates derived data), `format.ts`.
- **components/** – UI kit, layout (sidebar, mobile drawer, theme toggle), Recharts wrappers that read CSS variables (charts follow the theme), JOCASTA chat/cards/launcher.
- **pages/** – lazy-loaded routes.

## Key decisions
- **Money as strings over the wire**: Pydantic serialises `Decimal` as strings; the UI converts to number only for display.
- **Soft delete** for transactions, budgets and goals (`deleted_at`) + `audit_logs` for history; account deletion is a hard cascade delete for privacy.
- **Logout** bumps `users.token_version`, invalidating all issued JWTs without a denylist table.
- **Recommendations** are rows in `budget_recommendations` with `status`; only an explicit decision endpoint turns one into a budget.
- **Statement preview** stores extracted rows (not the file) in `uploaded_files.extracted_rows` until approve/reject, then clears them.
