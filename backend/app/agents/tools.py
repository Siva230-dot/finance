"""Typed LangChain tools for JOCASTA.

Security model:
* Tools are closures bound to a ToolContext created by the backend from the authenticated JWT user.
  No tool accepts a user_id argument, so the LLM can never act for another user.
* Tools call the same service layer as the REST API (parameterised SQLAlchemy only, no raw SQL).
* Mutations never execute directly: they create a PendingConfirmation and return its summary.
  The mutation runs only after the user confirms (see actions.execute_confirmation).
"""
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.models import PendingConfirmation, User
from app.services import analytics, budgets as budget_svc, reports as report_svc, savings as savings_svc
from app.services import transactions as tx_svc
from app.services.categories import category_by_slug, resolve_category, rule_categorize
from app.services.money import add_months, month_end, month_start, to_money


@dataclass
class ToolContext:
    db: Session
    user: User
    conversation_id: uuid.UUID | None = None
    cards: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    pending: list[dict] = field(default_factory=list)

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.id


# ---------------------------------------------------------------- parsing helpers
def parse_when(value: str | None, default: date | None = None) -> date:
    today = date.today()
    if not value:
        return default or today
    v = value.strip().lower()
    if v in ("today", "now"):
        return today
    if v == "yesterday":
        return today - timedelta(days=1)
    if v == "tomorrow":
        return today + timedelta(days=1)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(value.strip().replace(",", ""), fmt).date()
        except ValueError:
            continue
    raise AppError(422, "validation_error", f"Could not understand the date '{value}'. Use YYYY-MM-DD.")


def parse_month(value: str | None) -> date:
    today = date.today()
    if not value:
        return month_start(today)
    v = value.strip().lower()
    if v in ("this month", "current", "current month", "this"):
        return month_start(today)
    if v in ("last month", "previous month", "previous", "last"):
        return add_months(month_start(today), -1)
    if v in ("next month", "next"):
        return add_months(month_start(today), 1)
    for fmt in ("%Y-%m", "%Y-%m-%d", "%B %Y", "%b %Y"):
        try:
            return month_start(datetime.strptime(value.strip(), fmt).date())
        except ValueError:
            continue
    raise AppError(422, "validation_error", f"Could not understand the month '{value}'. Use YYYY-MM.")


def _money_str(v) -> str:
    if v is None:
        return v
    if isinstance(v, (int, float, Decimal)):
        return str(v)
    return re.sub(r"[₹,\s]|(?i:rs\.?|inr)", "", str(v))


class _Model(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def _coerce_numbers(cls, v, info):
        if info.field_name in ("amount", "target_amount", "current_amount", "new_amount", "min_amount", "max_amount") and v is not None:
            return _money_str(v)
        return v


# ---------------------------------------------------------------- schemas
class CreateTransactionArgs(_Model):
    description: str = Field(description="Short description, e.g. 'Groceries at DMart'")
    amount: str = Field(description="Positive amount as a decimal string, e.g. '500' or '1299.50'")
    type: str = Field(description="'expense' or 'income'")
    category: str | None = Field(default=None, description="Category name, e.g. 'Food and Groceries'. Omit to auto-categorize.")
    date: str | None = Field(default=None, description="YYYY-MM-DD, 'today' or 'yesterday'. Defaults to today.")
    payment_method: str | None = Field(default=None, description="Optional: UPI, Card, Cash, NetBanking")
    notes: str | None = None


class ListTransactionsArgs(_Model):
    search: str | None = Field(default=None, description="Text to match in description/notes/category")
    category: str | None = Field(default=None, description="Category name to filter by")
    type: str | None = Field(default=None, description="'income' or 'expense'")
    start_date: str | None = Field(default=None, description="YYYY-MM-DD inclusive")
    end_date: str | None = Field(default=None, description="YYYY-MM-DD inclusive")
    min_amount: str | None = None
    max_amount: str | None = None
    sort: str = Field(default="date", description="date | amount")
    order: str = Field(default="desc", description="asc | desc")
    limit: int = Field(default=10, ge=1, le=50)


class TxIdArgs(_Model):
    transaction_id: str = Field(description="Transaction id returned by list_transactions")


class UpdateTransactionArgs(_Model):
    transaction_id: str = Field(description="Transaction id returned by list_transactions")
    description: str | None = None
    amount: str | None = None
    type: str | None = None
    category: str | None = None
    date: str | None = None
    payment_method: str | None = None
    notes: str | None = None


class CreateBudgetArgs(_Model):
    category: str = Field(description="Expense category name, e.g. 'Food and Groceries'")
    amount: str = Field(description="Monthly budget amount as decimal string")
    month: str | None = Field(default=None, description="YYYY-MM, 'this month' or 'next month'. Defaults to this month.")


class ListBudgetsArgs(_Model):
    month: str | None = Field(default=None, description="YYYY-MM or 'this month'. Defaults to this month.")
    only_exceeded: bool = Field(default=False, description="Only return budgets that are exceeded")


class UpdateBudgetArgs(_Model):
    budget_id: str | None = Field(default=None, description="Budget id from list_budgets")
    category: str | None = Field(default=None, description="Category name when id is unknown")
    month: str | None = None
    amount: str = Field(description="New monthly amount")


class DeleteBudgetArgs(_Model):
    budget_id: str | None = None
    category: str | None = None
    month: str | None = None


class CreateGoalArgs(_Model):
    name: str
    target_amount: str
    current_amount: str | None = Field(default=None, description="Amount already saved, default 0")
    target_date: str | None = Field(default=None, description="YYYY-MM-DD deadline (optional)")


class ListGoalsArgs(_Model):
    include_archived: bool = False


class UpdateGoalArgs(_Model):
    goal_id: str | None = Field(default=None, description="Goal id from list_savings_goals")
    goal_name: str | None = Field(default=None, description="Existing goal name when id is unknown")
    new_name: str | None = None
    target_amount: str | None = None
    target_date: str | None = None
    status: str | None = Field(default=None, description="active | completed | archived")


class GoalRefArgs(_Model):
    goal_id: str | None = None
    goal_name: str | None = None


class ContributionArgs(_Model):
    goal_id: str | None = None
    goal_name: str | None = None
    amount: str = Field(description="Amount saved (negative to withdraw)")
    date: str | None = None
    note: str | None = None


class PeriodArgs(_Model):
    month: str | None = Field(default=None, description="YYYY-MM, 'this month' or 'last month'. Defaults to this month.")
    start_date: str | None = Field(default=None, description="Custom range start YYYY-MM-DD")
    end_date: str | None = Field(default=None, description="Custom range end YYYY-MM-DD")
    category: str | None = Field(default=None, description="Optional category to focus on")


class AnalyzeArgs(_Model):
    month: str | None = None
    compare_previous: bool = Field(default=True, description="Include month-over-month comparison")


class RecommendArgs(_Model):
    month: str | None = Field(default=None, description="Target month YYYY-MM. Defaults to next month.")
    category: str | None = None


class ReportArgs(_Model):
    report_type: str = Field(default="monthly", description="'monthly' or 'annual'")
    period: str | None = Field(default=None, description="YYYY-MM for monthly, YYYY for annual. Defaults to current.")


class CategorizeArgs(_Model):
    description: str
    type: str = "expense"


# ---------------------------------------------------------------- confirmation
def _confirm(ctx: ToolContext, action: str, payload: dict, summary: dict) -> dict:
    pc = PendingConfirmation(
        user_id=ctx.user_id,
        conversation_id=ctx.conversation_id,
        action=action,
        payload=payload,
        summary=summary,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.CONFIRMATION_TTL_MINUTES),
    )
    ctx.db.add(pc)
    ctx.db.commit()
    card = {"type": "confirmation", "confirmation_id": str(pc.id), "action": action, "summary": summary, "status": "pending"}
    ctx.cards.append(card)
    ctx.pending.append(card)
    return {
        "status": "confirmation_required",
        "confirmation_id": str(pc.id),
        "summary": summary,
        "instruction": "Not executed yet. Show the summary to the user and ask them to confirm or cancel.",
    }


def _uuid(value: str, what: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        raise AppError(422, "validation_error", f"Invalid {what} id. Look it up first with the list tool.")


def _category(ctx: ToolContext, name: str | None):
    if not name:
        return None
    cat = resolve_category(ctx.db, ctx.user_id, name)
    if not cat:
        raise AppError(422, "validation_error", f"Unknown category '{name}'.")
    return cat


def _find_goal(ctx: ToolContext, goal_id: str | None, goal_name: str | None):
    if goal_id:
        return savings_svc.get_goal(ctx.db, ctx.user_id, _uuid(goal_id, "goal"))
    if not goal_name:
        raise AppError(422, "validation_error", "Which savings goal? Provide the goal name or id.")
    goals = savings_svc.list_goals(ctx.db, ctx.user_id)
    low = goal_name.lower().strip()
    matches = [g for g in goals if g.name.lower() == low] or [g for g in goals if low in g.name.lower() or g.name.lower() in low]
    if not matches:
        raise AppError(404, "not_found", f"No savings goal matching '{goal_name}'.")
    if len(matches) > 1:
        raise AppError(409, "ambiguous", "Several goals match: " + ", ".join(f"{g.name} (id {g.id})" for g in matches) + ". Ask which one.")
    return matches[0]


def _find_budget(ctx: ToolContext, budget_id: str | None, category: str | None, month: str | None):
    if budget_id:
        return budget_svc.get_budget(ctx.db, ctx.user_id, _uuid(budget_id, "budget"))
    cat = _category(ctx, category)
    if not cat:
        raise AppError(422, "validation_error", "Which budget? Provide the category.")
    b = budget_svc.find_budget(ctx.db, ctx.user_id, cat.id, parse_month(month))
    if not b:
        raise AppError(404, "not_found", f"No {cat.name} budget for {parse_month(month):%B %Y}.")
    return b


def _period(args: PeriodArgs | AnalyzeArgs) -> tuple[date, date]:
    sd, ed = getattr(args, "start_date", None), getattr(args, "end_date", None)
    if sd or ed:
        s = parse_when(sd) if sd else month_start(date.today())
        e = parse_when(ed) if ed else date.today()
        return s, e
    m = parse_month(args.month)
    return m, month_end(m)


# ---------------------------------------------------------------- tool factory
def build_tools(ctx: ToolContext) -> dict[str, StructuredTool]:
    db, uid = ctx.db, ctx.user_id
    cur = ctx.user.currency

    def create_transaction(**kw) -> dict:
        a = CreateTransactionArgs(**kw)
        amount = to_money(a.amount)
        if amount <= 0:
            raise AppError(422, "validation_error", "Amount must be positive.")
        t = a.type.lower().strip()
        if t not in ("income", "expense"):
            raise AppError(422, "validation_error", "type must be 'income' or 'expense'.")
        when = parse_when(a.date)
        cat = _category(ctx, a.category)
        if cat is None:
            guess = rule_categorize(a.description, t)
            cat = category_by_slug(db, uid, guess.slug if guess else ("income" if t == "income" else "other"))
        payload = {"description": a.description[:255], "amount": str(amount), "type": t, "category_id": str(cat.id),
                   "transaction_date": when.isoformat(), "payment_method": a.payment_method, "notes": a.notes}
        summary = {"title": "New transaction", "fields": {"Description": a.description, "Amount": f"{cur} {amount}", "Type": t.title(),
                   "Category": cat.name, "Date": when.isoformat(), **({"Payment": a.payment_method} if a.payment_method else {})}}
        if settings.ASSISTANT_CONFIRM_CREATES:
            return _confirm(ctx, "create_transaction", payload, summary)
        from app.agents.actions import execute_action

        return execute_action(db, ctx.user, "create_transaction", payload, ctx)

    def list_transactions(**kw) -> dict:
        a = ListTransactionsArgs(**kw)
        cat = _category(ctx, a.category)
        items, total = tx_svc.query_transactions(
            db, uid, search=a.search, category_id=cat.id if cat else None, tx_type=a.type,
            start=parse_when(a.start_date) if a.start_date else None, end=parse_when(a.end_date) if a.end_date else None,
            min_amount=to_money(a.min_amount) if a.min_amount else None, max_amount=to_money(a.max_amount) if a.max_amount else None,
            sort=a.sort, order=a.order, page_size=a.limit,
        )
        rows = [tx_svc.serialize_tx(t) for t in items]
        ctx.cards.append({"type": "transactions", "items": rows, "total": total})
        total_amount = sum((t.amount for t in items), Decimal("0"))
        return {"total_matching": total, "returned": len(rows), "sum_of_returned": str(total_amount), "transactions": rows}

    def get_transaction(**kw) -> dict:
        a = TxIdArgs(**kw)
        t = tx_svc.get_transaction(db, uid, _uuid(a.transaction_id, "transaction"))
        row = tx_svc.serialize_tx(t)
        ctx.cards.append({"type": "transactions", "items": [row], "total": 1})
        return row

    def update_transaction(**kw) -> dict:
        a = UpdateTransactionArgs(**kw)
        t = tx_svc.get_transaction(db, uid, _uuid(a.transaction_id, "transaction"))
        changes: dict = {}
        before = tx_svc.serialize_tx(t)
        if a.description:
            changes["description"] = a.description
        if a.amount:
            changes["amount"] = str(to_money(a.amount))
        if a.type:
            changes["type"] = a.type.lower()
        if a.category:
            changes["category_id"] = str(_category(ctx, a.category).id)
        if a.date:
            changes["transaction_date"] = parse_when(a.date).isoformat()
        if a.payment_method:
            changes["payment_method"] = a.payment_method
        if a.notes:
            changes["notes"] = a.notes
        if not changes:
            raise AppError(422, "validation_error", "Nothing to update was provided.")
        readable = {k.replace("_id", "").replace("transaction_", "").title(): (_category(ctx, a.category).name if k == "category_id" else v) for k, v in changes.items()}
        summary = {"title": "Update transaction", "record": before, "changes": readable}
        return _confirm(ctx, "update_transaction", {"transaction_id": str(t.id), "changes": changes}, summary)

    def delete_transaction(**kw) -> dict:
        a = TxIdArgs(**kw)
        t = tx_svc.get_transaction(db, uid, _uuid(a.transaction_id, "transaction"))
        summary = {"title": "Delete transaction", "record": tx_svc.serialize_tx(t), "warning": "The transaction will be removed from all reports (kept in audit history)."}
        return _confirm(ctx, "delete_transaction", {"transaction_id": str(t.id)}, summary)

    def create_budget(**kw) -> dict:
        a = CreateBudgetArgs(**kw)
        cat = _category(ctx, a.category)
        month = parse_month(a.month)
        amount = to_money(a.amount)
        if amount <= 0:
            raise AppError(422, "validation_error", "Budget must be positive.")
        if cat.kind == "income":
            raise AppError(422, "validation_error", "Budgets apply to expense categories only.")
        existing = budget_svc.find_budget(db, uid, cat.id, month)
        if existing:
            return {"status": "exists", "budget_id": str(existing.id), "current_amount": str(existing.amount),
                    "message": "A budget already exists for this category and month; use update_budget instead."}
        summary = {"title": "New budget", "fields": {"Category": cat.name, "Month": f"{month:%B %Y}", "Amount": f"{cur} {amount}"}}
        return _confirm(ctx, "create_budget", {"category_id": str(cat.id), "month": month.isoformat(), "amount": str(amount)}, summary)

    def list_budgets(**kw) -> dict:
        a = ListBudgetsArgs(**kw)
        month = parse_month(a.month)
        rows = budget_svc.budget_status(db, uid, month)
        if a.only_exceeded:
            rows = [r for r in rows if r["status"] == "exceeded"]
        ctx.cards.append({"type": "budgets", "month": month.isoformat(), "items": rows})
        return {"month": month.isoformat(), "budgets": rows}

    def update_budget(**kw) -> dict:
        a = UpdateBudgetArgs(**kw)
        b = _find_budget(ctx, a.budget_id, a.category, a.month)
        amount = to_money(a.amount)
        if amount <= 0:
            raise AppError(422, "validation_error", "Budget must be positive.")
        summary = {"title": "Update budget", "fields": {"Category": b.category.name, "Month": f"{b.month:%B %Y}",
                   "Current": f"{cur} {b.amount}", "New amount": f"{cur} {amount}"}}
        return _confirm(ctx, "update_budget", {"budget_id": str(b.id), "amount": str(amount)}, summary)

    def delete_budget(**kw) -> dict:
        a = DeleteBudgetArgs(**kw)
        b = _find_budget(ctx, a.budget_id, a.category, a.month)
        summary = {"title": "Delete budget", "fields": {"Category": b.category.name, "Month": f"{b.month:%B %Y}", "Amount": f"{cur} {b.amount}"}}
        return _confirm(ctx, "delete_budget", {"budget_id": str(b.id)}, summary)

    def create_savings_goal(**kw) -> dict:
        a = CreateGoalArgs(**kw)
        target = to_money(a.target_amount)
        current = to_money(a.current_amount) if a.current_amount else Decimal("0.00")
        td = parse_when(a.target_date) if a.target_date else None
        if target <= 0:
            raise AppError(422, "validation_error", "Target must be positive.")
        if td and td <= date.today():
            raise AppError(422, "validation_error", "Target date must be in the future.")
        p = savings_svc.goal_progress(target, current, td)
        fields = {"Goal": a.name, "Target": f"{cur} {target}", "Already saved": f"{cur} {current}"}
        if td:
            fields["Target date"] = td.isoformat()
            if p["required_monthly"]:
                fields["Required monthly"] = f"{cur} {p['required_monthly']}"
        return _confirm(ctx, "create_savings_goal",
                        {"name": a.name, "target_amount": str(target), "current_amount": str(current), "target_date": td.isoformat() if td else None},
                        {"title": "New savings goal", "fields": fields})

    def list_savings_goals(**kw) -> dict:
        a = ListGoalsArgs(**kw)
        goals = [savings_svc.serialize_goal(g) for g in savings_svc.list_goals(db, uid, include_archived=a.include_archived)]
        ctx.cards.append({"type": "goals", "items": goals})
        total_remaining = sum((Decimal(g["remaining_amount"]) for g in goals if g["status"] == "active"), Decimal("0"))
        return {"goals": goals, "total_remaining_active": str(total_remaining)}

    def update_savings_goal(**kw) -> dict:
        a = UpdateGoalArgs(**kw)
        g = _find_goal(ctx, a.goal_id, a.goal_name)
        changes, readable = {}, {}
        if a.new_name:
            changes["name"] = readable["Name"] = a.new_name
        if a.target_amount:
            changes["target_amount"] = str(to_money(a.target_amount))
            readable["Target"] = f"{cur} {changes['target_amount']}"
        if a.target_date:
            changes["target_date"] = readable["Target date"] = parse_when(a.target_date).isoformat()
        if a.status:
            changes["status"] = readable["Status"] = a.status
        if not changes:
            raise AppError(422, "validation_error", "Nothing to update was provided.")
        summary = {"title": "Update savings goal", "record": savings_svc.serialize_goal(g), "changes": readable}
        return _confirm(ctx, "update_savings_goal", {"goal_id": str(g.id), "changes": changes}, summary)

    def delete_savings_goal(**kw) -> dict:
        a = GoalRefArgs(**kw)
        g = _find_goal(ctx, a.goal_id, a.goal_name)
        summary = {"title": "Delete savings goal", "record": savings_svc.serialize_goal(g), "warning": "The goal and its progress will be removed."}
        return _confirm(ctx, "delete_savings_goal", {"goal_id": str(g.id)}, summary)

    def record_savings_contribution(**kw) -> dict:
        a = ContributionArgs(**kw)
        g = _find_goal(ctx, a.goal_id, a.goal_name)
        amount = to_money(a.amount)
        if amount == 0:
            raise AppError(422, "validation_error", "Amount cannot be zero.")
        when = parse_when(a.date)
        summary = {"title": "Record contribution", "fields": {"Goal": g.name, "Amount": f"{cur} {amount}", "Date": when.isoformat(),
                   "New total": f"{cur} {g.current_amount + amount}"}}
        return _confirm(ctx, "record_savings_contribution", {"goal_id": str(g.id), "amount": str(amount), "date": when.isoformat(), "note": a.note}, summary)

    def get_financial_summary(**kw) -> dict:
        a = PeriodArgs(**kw)
        s, e = _period(a)
        summary = analytics.period_summary(db, uid, s, e)
        cats = analytics.category_breakdown(db, uid, s, e)
        if a.category:
            cat = _category(ctx, a.category)
            cats = [c for c in cats if c["category_id"] == str(cat.id)] or [{"category": cat.name, "amount": "0.00", "count": 0, "share": "0.0"}]
        result = {**summary, "currency": cur, "expense_by_category": cats, "total_balance_all_time": str(analytics.total_balance(db, uid))}
        ctx.cards.append({"type": "summary", "data": {**summary, "currency": cur, "top": cats[:5]}})
        return result

    def analyze_spending(**kw) -> dict:
        a = AnalyzeArgs(**kw)
        m = parse_month(a.month)
        s, e = m, month_end(m)
        summary = analytics.monthly_summary(db, uid, m)
        cats = analytics.category_breakdown(db, uid, s, e)
        result = {"month": m.isoformat(), "currency": cur, "summary": summary, "categories": cats,
                  "average_monthly_expense_prev_3": str(analytics.average_monthly_expense(db, uid, m)),
                  "budgets": budget_svc.budget_status(db, uid, m)}
        if a.compare_previous:
            result["month_over_month"] = analytics.month_over_month(db, uid, m)
        inc, exp = Decimal(summary["income"]), Decimal(summary["expenses"])
        result["potential_savings_note"] = (
            f"Recorded income minus expenses this month is {inc - exp}." if inc > 0 else "No income recorded this month."
        )
        ctx.cards.append({"type": "analysis", "data": {"summary": summary, "categories": cats[:6],
                                                        "mom": result.get("month_over_month", {}).get("expenses")}})
        return result

    def calculate_budget_recommendation(**kw) -> dict:
        a = RecommendArgs(**kw)
        month = parse_month(a.month) if a.month else add_months(month_start(date.today()), 1)
        cat = _category(ctx, a.category)
        recs = budget_svc.generate_recommendations(db, uid, month, cat.id if cat else None)
        items = [{"id": str(r.id), "category": r.category.name, "proposed_amount": str(r.proposed_amount), "reason": r.reason,
                  "expected_effect": r.expected_effect, "confidence": r.confidence, "limitations": r.limitations,
                  "basis": {k: r.historical_basis[k] for k in ("weighted_average", "mean", "trend_per_month", "months_with_data")}}
                 for r in recs]
        ctx.cards.append({"type": "recommendations", "month": month.isoformat(), "items": items})
        if not items:
            return {"month": month.isoformat(), "recommendations": [], "note": "Not enough expense history to recommend budgets yet."}
        return {"month": month.isoformat(), "recommendations": items,
                "note": "These are proposals only. They are saved as budgets only when the user approves them on the card or the Budgets page."}

    def generate_financial_report(**kw) -> dict:
        a = ReportArgs(**kw)
        rtype = "annual" if a.report_type.lower().startswith("ann") else "monthly"
        if rtype == "annual":
            period = date(int(a.period[:4]), 1, 1) if a.period else date(date.today().year, 1, 1)
        else:
            period = parse_month(a.period)
        payload = report_svc.build_report(db, uid, rtype, period)
        ctx.cards.append({"type": "report", "report_type": rtype, "period": period.isoformat()[:7 if rtype == "monthly" else 4],
                          "report_id": payload.get("report_id"), "summary": payload["summary"]})
        return {k: v for k, v in payload.items() if k in ("title", "summary", "category_breakdown", "months", "budgets", "goals", "period_start", "period_end")}

    def suggest_category(**kw) -> dict:
        a = CategorizeArgs(**kw)
        g = rule_categorize(a.description, a.type)
        if g:
            cat = category_by_slug(db, uid, g.slug)
            return {"category": cat.name, "source": "rule", "confidence": str(g.confidence)}
        return {"category": None, "source": "none", "note": "No rule matched; choose the best category from the list and say it is a suggestion."}

    specs = [
        (create_transaction, CreateTransactionArgs, "Prepare a new income/expense transaction. Requires user confirmation before it is saved."),
        (list_transactions, ListTransactionsArgs, "Search and list the user's transactions with filters; also use to find ids before update/delete and to total spending."),
        (get_transaction, TxIdArgs, "Get one transaction by id."),
        (update_transaction, UpdateTransactionArgs, "Prepare an update to an existing transaction (requires confirmation). Find the id with list_transactions first."),
        (delete_transaction, TxIdArgs, "Prepare deletion of ONE specific transaction (requires confirmation). Never guess the id."),
        (create_budget, CreateBudgetArgs, "Prepare a monthly category budget (requires confirmation)."),
        (list_budgets, ListBudgetsArgs, "List budgets with spent, remaining, utilisation and status (on_track/at_risk/exceeded)."),
        (update_budget, UpdateBudgetArgs, "Prepare a change to a budget amount (requires confirmation)."),
        (delete_budget, DeleteBudgetArgs, "Prepare deletion of a budget (requires confirmation)."),
        (create_savings_goal, CreateGoalArgs, "Prepare a new savings goal (requires confirmation)."),
        (list_savings_goals, ListGoalsArgs, "List savings goals with progress, remaining amount and required monthly saving."),
        (update_savings_goal, UpdateGoalArgs, "Prepare changes to a savings goal (requires confirmation)."),
        (delete_savings_goal, GoalRefArgs, "Prepare deletion of a savings goal (requires confirmation)."),
        (record_savings_contribution, ContributionArgs, "Prepare recording money saved toward a goal (requires confirmation)."),
        (get_financial_summary, PeriodArgs, "Exact income, expenses, savings, savings rate and category totals for a month or date range."),
        (analyze_spending, AnalyzeArgs, "Deep spending analysis for a month incl. category breakdown, month-over-month change and budget status."),
        (calculate_budget_recommendation, RecommendArgs, "Compute data-driven budget recommendations from spending history (deterministic). Does not save budgets."),
        (generate_financial_report, ReportArgs, "Generate a monthly or annual financial report from stored records."),
        (suggest_category, CategorizeArgs, "Suggest a category for a transaction description using the rule engine."),
    ]
    tools = {}
    for fn, schema, desc in specs:
        tools[fn.__name__] = StructuredTool.from_function(func=fn, name=fn.__name__, description=desc, args_schema=schema)
    return tools


TOOLSETS: dict[str, list[str]] = {
    "transaction": ["create_transaction", "list_transactions", "get_transaction", "update_transaction", "delete_transaction",
                    "get_financial_summary", "suggest_category"],
    "categorization": ["list_transactions", "update_transaction", "suggest_category"],
    "analysis": ["get_financial_summary", "analyze_spending", "list_transactions", "list_budgets", "generate_financial_report",
                 "list_savings_goals"],
    "budget": ["create_budget", "list_budgets", "update_budget", "delete_budget", "calculate_budget_recommendation",
               "get_financial_summary", "analyze_spending"],
    "savings": ["create_savings_goal", "list_savings_goals", "update_savings_goal", "delete_savings_goal",
                "record_savings_contribution", "get_financial_summary"],
    "general": ["get_financial_summary", "list_transactions", "list_budgets", "list_savings_goals"],
}
