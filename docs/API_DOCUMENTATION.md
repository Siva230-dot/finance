# API Documentation

Base path: `/api/v1`. Interactive docs in development at `/api/docs` (disabled when `APP_ENV=production`).
Auth: `Authorization: Bearer <access_token>` on everything except `/health`, `/auth/register`, `/auth/login`.
Errors: `{"error": {"code": "validation_error", "message": "...", "details": [...]}}`. Money fields are decimal strings.

| Method & path | Description |
|---|---|
| `GET /health` | DB + LLM configuration status (503 if DB unavailable) |
| `POST /auth/register` | `{email, full_name, password, currency}` → `{access_token, expires_in, user}` (10/min) |
| `POST /auth/login` | `{email, password}` → token (10/min) |
| `POST /auth/logout` | Revokes all tokens for the user |
| `GET/PATCH /users/me` | Profile; PATCH `{full_name?, currency?, theme_preference?}` |
| `POST /users/me/password` | `{current_password, new_password}` → new token |
| `GET /users/me/export` | JSON export of all user data |
| `DELETE /users/me` | `{password, confirm:"DELETE"}` hard-deletes account |
| `GET/POST /categories`, `DELETE /categories/{id}` | System + custom categories |
| `GET /transactions` | `search, category_id, type, start_date, end_date, min_amount, max_amount, sort(date/amount/description/created), order, page, page_size` |
| `POST /transactions` | `{description, amount, type, transaction_date, category_id?, payment_method?, notes?, is_recurring, recurrence_interval?}` |
| `GET/PATCH/DELETE /transactions/{id}` | Read / partial update / soft delete |
| `GET /transactions/export` | CSV with current filters |
| `GET /transactions/duplicates` | Groups of identical (date, amount, type, description) |
| `POST /transactions/recurring/run` | Create due recurring occurrences |
| `GET /budgets?month=` | Budgets with spent/remaining/utilisation/status, previous month, totals |
| `POST /budgets`, `PATCH/DELETE /budgets/{id}` | CRUD |
| `POST /budgets/copy-previous?month=` | Copy last month's budgets |
| `GET /budgets/recommendations?month=` | Pending recommendations |
| `POST /budgets/recommendations/generate` | `{month?, category_id?}` compute proposals |
| `POST /budgets/recommendations/{id}/decision` | `{approve, amount?}` — the only way a proposal becomes a budget |
| `GET/POST /savings`, `GET/PATCH/DELETE /savings/{id}` | Goals with progress maths |
| `POST /savings/{id}/contributions` | `{amount (negative = withdrawal), contribution_date?, note?}` |
| `GET /analytics/overview?month=&months=` | Dashboard payload |
| `GET /analytics/summary`, `/categories`, `/trends`, `/comparison` | Individual analytics |
| `GET /reports/{monthly|annual}` | Report JSON (`month=` or `year=`) |
| `GET /reports/{type}/download?format=pdf|csv` | File download; saved to history |
| `GET /reports` | Recent report history |
| `POST /uploads/statements` | multipart `file` (+`use_ai`) → preview rows (10/min) |
| `POST /uploads/statements/{id}/approve` | `{selected_indexes, category_overrides}` |
| `POST /uploads/statements/{id}/reject` | Discard preview |
| `GET /assistant/status` | Whether Groq is configured |
| `POST /assistant/chat` | `{message, conversation_id?}` → assistant message with `meta.cards`, `meta.tool_events` (20/min) |
| `GET /assistant/conversations`, `GET …/{id}/messages`, `DELETE …/{id}` | History |
| `POST /assistant/confirmations/{id}/confirm|cancel` | Resolve a pending action |
| `GET /assistant/suggestions` | Suggested prompts |
