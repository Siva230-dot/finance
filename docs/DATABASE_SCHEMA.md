# Database Schema

PostgreSQL, managed by Alembic (`backend/alembic/versions/20261118_0001_initial_schema.py`). All primary keys are UUIDs. Money columns are `NUMERIC(14,2)`. Timestamps are `timestamptz`.

| Table | Purpose | Key columns / constraints |
|---|---|---|
| `users` | Accounts | `email` unique, `password_hash` (Argon2id), `currency`, `theme_preference`, `token_version` |
| `categories` | System (user_id NULL) + custom categories | partial unique `(name) WHERE user_id IS NULL`, `(user_id,name) WHERE user_id IS NOT NULL`; `kind ∈ income/expense/both` |
| `transactions` | Ledger | FK user (cascade), FK category (restrict); `amount > 0`; `type ∈ income/expense`; `categorization_source`, `categorization_confidence`; `dedupe_hash`; recurrence fields; `deleted_at`; indexes `(user_id, transaction_date)`, `(user_id, category_id)`, `(user_id, dedupe_hash)` |
| `budgets` | Monthly category budgets | `month` = first of month; `amount > 0`; partial unique `(user_id, category_id, month) WHERE deleted_at IS NULL` |
| `savings_goals` | Goals | `target_amount > 0`, `current_amount >= 0`, `status ∈ active/completed/archived`, `deleted_at` |
| `savings_contributions` | Deposits/withdrawals | FK goal (cascade), `amount <> 0` |
| `budget_recommendations` | Proposals | `proposed_amount`, `historical_basis` JSONB, `reason`, `expected_effect`, `confidence`, `limitations`, `status ∈ pending/approved/rejected` |
| `financial_reports` | Generated report snapshots | `report_type`, period, `payload` JSONB |
| `uploaded_files` | Upload **metadata** + temporary extracted rows | `status`, `rows_extracted`, `rows_imported`, `extracted_rows` (cleared after decision) |
| `agent_conversations` | Chat threads per user | `title` |
| `agent_messages` | Chat messages | `role`, `content`, `metadata` JSONB (cards, tool events) |
| `audit_logs` | Change history | `actor ∈ user/jocasta/system`, `action`, `entity_type`, `entity_id`, `details` (no amounts or descriptions) |
| `pending_confirmations` | JOCASTA actions awaiting consent | `action`, `payload`, `summary`, `status ∈ pending/confirmed/cancelled/expired/failed`, `expires_at` (15 min) |

Every user-owned table has `user_id` with `ON DELETE CASCADE`, and every service query includes `WHERE user_id = :current_user`.

Commands:
```bash
alembic upgrade head          # apply
alembic downgrade -1          # roll back one
alembic revision --autogenerate -m "describe change"
```
