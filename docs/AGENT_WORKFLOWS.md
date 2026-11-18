# JOCASTA Agent Workflows

## Graph (LangGraph `StateGraph`)

```
START → supervisor ─┬─► transaction_agent ─┐
                    ├─► categorization_agent│      (tool calls & iterations ≤ AGENT_MAX_ITERATIONS)
                    ├─► analysis_agent      ├──► tools ──► back to the same agent
                    ├─► budget_agent        │
                    ├─► savings_agent       │      (final answer or limit reached)
                    └─► jocasta (general) ──┴──► finalize → END
```

**State** (`AgentState`): `user_request`, `user_context` (id/name/currency from the JWT session), `history`, `messages`, `intent`, `intent_source`, `iterations`, `tool_events`, `requires_confirmation`, `final_response`, `error`.

### Agents
| Agent | Tools |
|---|---|
| Supervisor | Keyword classifier first (no LLM cost); Groq classification only when ambiguous; a generic "general" label never overrides a domain keyword |
| Transaction | create/list/get/update/delete_transaction, get_financial_summary, suggest_category |
| Expense Categorization | list_transactions, update_transaction, suggest_category |
| Financial Analysis | get_financial_summary, analyze_spending, list_transactions, list_budgets, list_savings_goals, generate_financial_report |
| Budget Planning | create/list/update/delete_budget, calculate_budget_recommendation, get_financial_summary, analyze_spending |
| Savings Goal | create/list/update/delete_savings_goal, record_savings_contribution, get_financial_summary |
| JOCASTA (conversational) | read-only summary/list tools |

An agent calling a tool outside its toolset gets `"rejected"` and nothing runs.

## Tool security
- Tools are built per request as closures over `ToolContext(db, user)`; **no tool has a `user_id` parameter**, and any `user_id` the model invents is stripped before execution.
- Tools call the same services as the REST API (parameterised SQLAlchemy). The LLM cannot run SQL.
- Numeric work (totals, summaries, recommendations, goal maths) is deterministic Python; the LLM only explains it.

## Confirmation mechanism
1. A mutating tool (create/update/delete transaction, budget or goal; contributions) validates input, resolves the exact record, and stores a `pending_confirmations` row with a human-readable summary. It returns `status: confirmation_required` — nothing is written.
2. The UI renders a confirmation card (record + changes) with Confirm / Cancel.
3. The user presses Confirm, or replies "yes"/"no". Replies are matched with a strict regex and handled **without the LLM**.
4. `actions.confirm` claims the row (prevents double execution), executes via services, audits with `actor=jocasta`, and the reply is generated from the real result.
5. Pending actions expire after 15 minutes; cancelled/expired/confirmed actions cannot be re-run.
6. `finalize` rewrites any model text that claims success while an action is only pending.

Ambiguity: goal lookups by name that match several goals return an error listing the candidates; deletes take one explicit id found via `list_transactions`. There is no bulk-delete tool.

## Reliability
- `AGENT_MAX_ITERATIONS` (default 5) tool rounds; LangGraph `recursion_limit` as a backstop.
- `ChatGroq(timeout=GROQ_TIMEOUT_SECONDS, max_retries=GROQ_MAX_RETRIES)` retries 429/5xx with backoff.
- Rate-limit, timeout, auth and connection errors become friendly messages with `meta.error` codes; prepared confirmations survive the failure.
- Missing `GROQ_API_KEY` → JOCASTA explains it is not configured; the rest of the app works.
- History: last 12 messages of the current conversation are context only; the system prompt says figures must come from tools in the current turn.

## Manual verification
With `GROQ_API_KEY` set, try:
1. "Add ₹500 for groceries today" → confirmation card → "Yes" → transaction appears on the Transactions page.
2. "Show my last five expenses"
3. "Update my restaurant expense from ₹650 to ₹750" (after adding one)
4. "Create a monthly food budget of ₹4,000" → confirm
5. "Which categories have exceeded their budgets?"
6. "Create a laptop savings goal of ₹60,000" → confirm; "How much more do I need to save?"
7. "Compare this month with last month"; "Recommend budgets for next month"
8. "Delete my entertainment budget" → Cancel → budget remains
