"""Deterministic financial analytics computed in SQL with NUMERIC + Python Decimal. Never invents figures."""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Category, Transaction
from app.services.money import ZERO, add_months, month_end, month_start, pct, to_money


def _active(user_id: uuid.UUID):
    return (Transaction.user_id == user_id, Transaction.deleted_at.is_(None))


def _sum(db: Session, user_id: uuid.UUID, tx_type: str, start: date, end: date) -> Decimal:
    v = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            *_active(user_id), Transaction.type == tx_type, Transaction.transaction_date.between(start, end)
        )
    )
    return to_money(v or 0)


def period_summary(db: Session, user_id: uuid.UUID, start: date, end: date) -> dict:
    income = _sum(db, user_id, "income", start, end)
    expense = _sum(db, user_id, "expense", start, end)
    savings = income - expense
    count = db.scalar(select(func.count()).where(*_active(user_id), Transaction.transaction_date.between(start, end))) or 0
    return {
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "income": str(income),
        "expenses": str(expense),
        "savings": str(savings),
        "savings_rate": str(pct(savings, income)) if income > 0 else "0.0",
        "transaction_count": count,
    }


def monthly_summary(db: Session, user_id: uuid.UUID, month: date) -> dict:
    return period_summary(db, user_id, month_start(month), month_end(month))


def total_balance(db: Session, user_id: uuid.UUID) -> Decimal:
    v = db.scalar(
        select(
            func.coalesce(func.sum(case((Transaction.type == "income", Transaction.amount), else_=-Transaction.amount)), 0)
        ).where(*_active(user_id))
    )
    return to_money(v or 0)


def category_breakdown(db: Session, user_id: uuid.UUID, start: date, end: date, tx_type: str = "expense") -> list[dict]:
    rows = db.execute(
        select(Category.id, Category.name, Category.slug, Category.color, func.sum(Transaction.amount), func.count())
        .join(Category, Category.id == Transaction.category_id)
        .where(*_active(user_id), Transaction.type == tx_type, Transaction.transaction_date.between(start, end))
        .group_by(Category.id, Category.name, Category.slug, Category.color)
        .order_by(func.sum(Transaction.amount).desc())
    ).all()
    total = sum((to_money(r[4]) for r in rows), ZERO)
    return [
        {
            "category_id": str(r[0]),
            "category": r[1],
            "slug": r[2],
            "color": r[3],
            "amount": str(to_money(r[4])),
            "count": r[5],
            "share": str(pct(to_money(r[4]), total)),
        }
        for r in rows
    ]


def monthly_series(db: Session, user_id: uuid.UUID, end_month: date, months: int = 6) -> list[dict]:
    start = month_start(add_months(month_start(end_month), -(months - 1)))
    end = month_end(end_month)
    m = func.date_trunc("month", Transaction.transaction_date)
    rows = db.execute(
        select(m, Transaction.type, func.sum(Transaction.amount))
        .where(*_active(user_id), Transaction.transaction_date.between(start, end))
        .group_by(m, Transaction.type)
    ).all()
    data: dict[str, dict[str, Decimal]] = {}
    for month_dt, t, amount in rows:
        key = month_dt.date().isoformat() if hasattr(month_dt, "date") else str(month_dt)[:10]
        data.setdefault(key, {})[t] = to_money(amount)
    out = []
    for i in range(months):
        key = add_months(start, i).isoformat()
        inc, exp = data.get(key, {}).get("income", ZERO), data.get(key, {}).get("expense", ZERO)
        out.append({"month": key, "income": str(inc), "expenses": str(exp), "savings": str(inc - exp)})
    return out


def daily_trend(db: Session, user_id: uuid.UUID, start: date, end: date) -> list[dict]:
    end = min(end, max(date.today(), start))  # never plot future days of the current month
    rows = db.execute(
        select(Transaction.transaction_date, func.sum(Transaction.amount))
        .where(*_active(user_id), Transaction.type == "expense", Transaction.transaction_date.between(start, end))
        .group_by(Transaction.transaction_date)
        .order_by(Transaction.transaction_date)
    ).all()
    by_day = {d: to_money(a) for d, a in rows}
    out, cur, running = [], start, ZERO
    from datetime import timedelta

    while cur <= end:
        amt = by_day.get(cur, ZERO)
        running += amt
        out.append({"date": cur.isoformat(), "amount": str(amt), "cumulative": str(running)})
        cur += timedelta(days=1)
    return out


def month_over_month(db: Session, user_id: uuid.UUID, month: date) -> dict:
    cur_s, cur_e = month_start(month), month_end(month)
    prev = add_months(cur_s, -1)
    prev_s, prev_e = prev, month_end(prev)
    cur, prv = monthly_summary(db, user_id, cur_s), monthly_summary(db, user_id, prev_s)
    cur_cats = {c["slug"]: c for c in category_breakdown(db, user_id, cur_s, cur_e)}
    prev_cats = {c["slug"]: c for c in category_breakdown(db, user_id, prev_s, prev_e)}
    changes = []
    for slug in sorted(set(cur_cats) | set(prev_cats)):
        a = Decimal(cur_cats.get(slug, {}).get("amount", "0"))
        b = Decimal(prev_cats.get(slug, {}).get("amount", "0"))
        name = (cur_cats.get(slug) or prev_cats.get(slug))["category"]
        changes.append(
            {"category": name, "slug": slug, "current": str(a), "previous": str(b), "change": str(a - b),
             "change_percent": str(pct(a - b, b)) if b > 0 else None}
        )
    changes.sort(key=lambda c: abs(Decimal(c["change"])), reverse=True)

    def delta(k):
        a, b = Decimal(cur[k]), Decimal(prv[k])
        return {"current": str(a), "previous": str(b), "change": str(a - b), "change_percent": str(pct(a - b, b)) if b > 0 else None}

    return {
        "current_month": cur_s.isoformat(),
        "previous_month": prev_s.isoformat(),
        "income": delta("income"),
        "expenses": delta("expenses"),
        "savings": delta("savings"),
        "category_changes": changes,
    }


def average_monthly_expense(db: Session, user_id: uuid.UUID, month: date, months: int = 3) -> Decimal:
    """Average over the `months` complete months before `month` that have any data."""
    totals = []
    for i in range(1, months + 1):
        m = add_months(month_start(month), -i)
        s = monthly_summary(db, user_id, m)
        if s["transaction_count"]:
            totals.append(Decimal(s["expenses"]))
    if not totals:
        return ZERO
    return to_money(sum(totals) / len(totals))


def overview(db: Session, user_id: uuid.UUID, month: date, months: int = 6) -> dict:
    from app.services.budgets import budget_status
    from app.services.savings import goals_with_progress

    s, e = month_start(month), month_end(month)
    summary = monthly_summary(db, user_id, s)
    cats = category_breakdown(db, user_id, s, e)
    budgets = budget_status(db, user_id, s)
    goals = goals_with_progress(db, user_id)
    from app.services.transactions import query_transactions, serialize_tx

    recent, _ = query_transactions(db, user_id, page_size=6)
    return {
        "month": s.isoformat(),
        "total_balance": str(total_balance(db, user_id)),
        "summary": summary,
        "average_monthly_expense": str(average_monthly_expense(db, user_id, s)),
        "category_breakdown": cats,
        "top_categories": cats[:3],
        "monthly_series": monthly_series(db, user_id, s, months),
        "daily_trend": daily_trend(db, user_id, s, e),
        "budgets": budgets,
        "goals": goals,
        "recent_transactions": [serialize_tx(t) for t in recent],
        "insights": deterministic_insights(db, user_id, s, summary, cats, budgets),
    }


def deterministic_insights(db, user_id, month: date, summary: dict, cats: list[dict], budgets: list[dict]) -> list[dict]:
    """Rule-based observations derived strictly from stored numbers (shown as JOCASTA insights)."""
    out: list[dict] = []
    if summary["transaction_count"] == 0:
        return [{"tone": "neutral", "text": "No transactions recorded this month yet. Add one or import a statement to begin."}]
    income, expenses = Decimal(summary["income"]), Decimal(summary["expenses"])
    if income > 0:
        rate = Decimal(summary["savings_rate"])
        tone = "positive" if rate >= 20 else ("warning" if rate < 0 else "neutral")
        out.append({"tone": tone, "text": f"You have saved {rate}% of this month's recorded income so far."})
    if cats:
        top = cats[0]
        out.append({"tone": "neutral", "text": f"{top['category']} is your largest expense category at {top['share']}% of spending."})
    over = [b for b in budgets if b["status"] == "exceeded"]
    if over:
        names = ", ".join(b["category"]["name"] for b in over[:3])
        out.append({"tone": "warning", "text": f"Budget exceeded in: {names}."})
    mom = month_over_month(db, user_id, month)
    if mom["expenses"]["change_percent"] is not None:
        ch = Decimal(mom["expenses"]["change_percent"])
        if abs(ch) >= 10:
            direction = "higher" if ch > 0 else "lower"
            out.append({"tone": "warning" if ch > 0 else "positive", "text": f"Spending is {abs(ch)}% {direction} than last month."})
    if expenses > income and income > 0:
        out.append({"tone": "warning", "text": "Expenses currently exceed income for this month."})
    return out
