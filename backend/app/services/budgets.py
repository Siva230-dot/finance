"""Budgets, utilisation and deterministic recommendations (Scikit-learn trend + weighted averages)."""
import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

import numpy as np
from sklearn.linear_model import LinearRegression
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Budget, BudgetRecommendation
from app.services.analytics import category_breakdown
from app.services.audit import audit
from app.services.categories import get_category, list_categories
from app.services.money import ZERO, add_months, month_end, month_start, pct, to_money

DISCRETIONARY = {"shopping", "entertainment", "travel", "subscriptions", "food"}
LOOKBACK_MONTHS = 6


def _q(user_id):
    return select(Budget).where(Budget.user_id == user_id, Budget.deleted_at.is_(None))


def get_budget(db: Session, user_id: uuid.UUID, budget_id: uuid.UUID) -> Budget:
    b = db.scalar(_q(user_id).where(Budget.id == budget_id))
    if not b:
        raise AppError(404, "not_found", "Budget not found")
    return b


def find_budget(db: Session, user_id: uuid.UUID, category_id: uuid.UUID, month) -> Budget | None:
    return db.scalar(_q(user_id).where(Budget.category_id == category_id, Budget.month == month_start(month)))


def create_budget(db: Session, user_id: uuid.UUID, category_id: uuid.UUID, month, amount, notes=None, actor="user") -> Budget:
    cat = get_category(db, user_id, category_id)
    if cat.kind == "income":
        raise AppError(422, "validation_error", "Budgets can only be set for expense categories")
    if find_budget(db, user_id, cat.id, month):
        raise AppError(409, "conflict", f"A {cat.name} budget already exists for {month_start(month):%B %Y}. Update it instead.")
    b = Budget(user_id=user_id, category_id=cat.id, month=month_start(month), amount=to_money(amount), notes=notes)
    b.category = cat
    db.add(b)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "conflict", "A budget for this category and month already exists")
    audit(db, user_id, "budget.create", "budget", b.id, actor)
    db.commit()
    db.refresh(b)
    return b


def update_budget(db: Session, user_id: uuid.UUID, budget_id: uuid.UUID, amount=None, notes=None, actor="user") -> Budget:
    b = get_budget(db, user_id, budget_id)
    if amount is not None:
        amount = to_money(amount)
        if amount <= 0:
            raise AppError(422, "validation_error", "Budget amount must be greater than zero")
        b.amount = amount
    if notes is not None:
        b.notes = notes
    audit(db, user_id, "budget.update", "budget", b.id, actor)
    db.commit()
    db.refresh(b)
    return b


def delete_budget(db: Session, user_id: uuid.UUID, budget_id: uuid.UUID, actor="user") -> Budget:
    b = get_budget(db, user_id, budget_id)
    b.deleted_at = datetime.now(timezone.utc)
    audit(db, user_id, "budget.delete", "budget", b.id, actor)
    db.commit()
    return b


def _status(util: Decimal) -> str:
    if util > 100:
        return "exceeded"
    if util >= 85:
        return "at_risk"
    return "on_track"


def budget_status(db: Session, user_id: uuid.UUID, month) -> list[dict]:
    m = month_start(month)
    budgets = db.scalars(_q(user_id).where(Budget.month == m)).unique().all()
    spent = {c["category_id"]: Decimal(c["amount"]) for c in category_breakdown(db, user_id, m, month_end(m))}
    out = []
    for b in sorted(budgets, key=lambda x: x.category.name):
        s = spent.get(str(b.category_id), ZERO)
        util = pct(s, b.amount)
        out.append(
            {
                "id": str(b.id),
                "category": {"id": str(b.category.id), "name": b.category.name, "slug": b.category.slug, "color": b.category.color,
                             "kind": b.category.kind, "icon": b.category.icon, "is_system": b.category.is_system},
                "month": b.month.isoformat(),
                "amount": str(b.amount),
                "notes": b.notes,
                "spent": str(s),
                "remaining": str(b.amount - s),
                "utilization": str(util),
                "status": _status(util),
            }
        )
    return out


def _lookback_months(target_month) -> list:
    """Up to LOOKBACK complete months before the target, excluding the current (incomplete) month."""
    from datetime import date as _date

    current = month_start(_date.today())
    last = min(add_months(month_start(target_month), -1), add_months(current, -1))
    return [add_months(last, -i) for i in range(LOOKBACK_MONTHS - 1, -1, -1)]


def _history(db: Session, user_id: uuid.UUID, target_month) -> dict[str, dict]:
    """Category spend for each of the LOOKBACK complete months before target_month."""
    hist: dict[str, dict] = {}
    for m in _lookback_months(target_month):
        for c in category_breakdown(db, user_id, m, month_end(m)):
            h = hist.setdefault(c["category_id"], {"name": c["category"], "slug": c["slug"], "months": {}})
            h["months"][m.isoformat()] = Decimal(c["amount"])
    return hist


def _round_to(value: Decimal, step: Decimal = Decimal("50")) -> Decimal:
    return to_money((value / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step)


def compute_recommendation(name: str, slug: str, series: list[tuple[str, Decimal]], current_budget: Decimal | None) -> dict:
    """Pure, deterministic recommendation for one category. series = [(month, amount)] oldest->newest, zeros included."""
    active = [(m, a) for m, a in series if a > 0]
    n = len(active)
    amounts = [a for _, a in series]
    # Weighted average of the most recent three months (0.5, 0.3, 0.2), ignoring empty leading months.
    recent = amounts[-3:]
    weights = [Decimal("0.2"), Decimal("0.3"), Decimal("0.5")][-len(recent):]
    wsum = sum(weights)
    weighted = sum((a * w for a, w in zip(recent, weights)), ZERO) / wsum if wsum else ZERO
    mean = sum(amounts, ZERO) / len(amounts) if amounts else ZERO

    trend_per_month = ZERO
    if n >= 3:
        x = np.arange(len(amounts)).reshape(-1, 1)
        y = np.array([float(a) for a in amounts])
        model = LinearRegression().fit(x, y)
        trend_per_month = to_money(Decimal(str(round(float(model.coef_[0]), 2))))
    # Forecast = weighted average + half the monthly trend (dampened), never below 0.
    forecast = max(weighted + trend_per_month / 2, ZERO)
    discretionary = slug in DISCRETIONARY
    target = forecast * (Decimal("0.90") if discretionary and trend_per_month > 0 else Decimal("0.95") if discretionary else Decimal("1.00"))
    proposed = max(_round_to(target), Decimal("50.00"))

    if n >= 4:
        cv = Decimal(str(float(np.std([float(a) for a in amounts]) / float(mean)))) if mean > 0 else Decimal("1")
        confidence = "high" if cv < Decimal("0.25") else "medium"
    elif n >= 2:
        confidence = "medium" if n == 3 else "low"
    else:
        confidence = "low"

    trend_word = "rising" if trend_per_month > mean * Decimal("0.05") else "falling" if trend_per_month < -mean * Decimal("0.05") else "stable"
    reason = (
        f"Based on {n} month(s) of {name} spending: weighted recent average {to_money(weighted)}, "
        f"{LOOKBACK_MONTHS}-month mean {to_money(mean)}, trend {trend_word} ({trend_per_month:+} per month)."
    )
    if discretionary:
        reason += " As a discretionary category, the proposal includes a modest reduction target."
    saving = to_money(weighted - proposed)
    if saving > 0:
        effect = f"Keeping to this budget would spend about {saving} less than your recent average."
    else:
        effect = "This budget matches your recent spending pattern and should be realistic to follow."
    if current_budget is not None:
        effect += f" Your current budget is {current_budget}."
    limitations = None
    if n < 3:
        limitations = "Limited history: fewer than three months of data. Treat this as a starting point."
    elif trend_word != "stable":
        limitations = "Spending is trending, so next month may differ from the forecast."
    return {
        "proposed_amount": proposed,
        "basis": {
            "months": [{"month": m, "amount": str(a)} for m, a in series],
            "weighted_average": str(to_money(weighted)),
            "mean": str(to_money(mean)),
            "trend_per_month": str(trend_per_month),
            "months_with_data": n,
            "method": "weighted average (0.2/0.3/0.5) + 50% of linear-regression trend; discretionary categories reduced 5–10%",
        },
        "reason": reason,
        "expected_effect": effect,
        "confidence": confidence,
        "limitations": limitations,
    }


def generate_recommendations(db: Session, user_id: uuid.UUID, target_month, category_id: uuid.UUID | None = None) -> list[BudgetRecommendation]:
    target = month_start(target_month)
    hist = _history(db, user_id, target)
    months = [m.isoformat() for m in _lookback_months(target)]
    # replace previous pending recommendations for the same month
    for old in db.scalars(
        select(BudgetRecommendation).where(
            BudgetRecommendation.user_id == user_id, BudgetRecommendation.month == target, BudgetRecommendation.status == "pending"
        )
    ):
        if category_id is None or old.category_id == category_id:
            db.delete(old)
    recs = []
    for cid, h in hist.items():
        if category_id and cid != str(category_id):
            continue
        if h["slug"] in ("income", "savings", "investments"):
            continue
        series = [(m, h["months"].get(m, ZERO)) for m in months]
        existing = find_budget(db, user_id, uuid.UUID(cid), target)
        r = compute_recommendation(h["name"], h["slug"], series, existing.amount if existing else None)
        rec = BudgetRecommendation(
            user_id=user_id, category_id=uuid.UUID(cid), month=target, proposed_amount=r["proposed_amount"],
            historical_basis=r["basis"], reason=r["reason"], expected_effect=r["expected_effect"],
            confidence=r["confidence"], limitations=r["limitations"],
        )
        db.add(rec)
        recs.append(rec)
    db.commit()
    for r in recs:
        db.refresh(r)
    return sorted(recs, key=lambda r: r.proposed_amount, reverse=True)


def list_recommendations(db: Session, user_id: uuid.UUID, month=None, status: str | None = "pending") -> list[BudgetRecommendation]:
    q = select(BudgetRecommendation).where(BudgetRecommendation.user_id == user_id)
    if month:
        q = q.where(BudgetRecommendation.month == month_start(month))
    if status:
        q = q.where(BudgetRecommendation.status == status)
    return list(db.scalars(q.order_by(BudgetRecommendation.proposed_amount.desc())).unique())


def decide_recommendation(db: Session, user_id: uuid.UUID, rec_id: uuid.UUID, approve: bool, amount: Decimal | None = None) -> tuple[BudgetRecommendation, Budget | None]:
    """Explicit user approval is the only path from a recommendation to a saved budget."""
    rec = db.scalar(select(BudgetRecommendation).where(BudgetRecommendation.id == rec_id, BudgetRecommendation.user_id == user_id))
    if not rec:
        raise AppError(404, "not_found", "Recommendation not found")
    if rec.status != "pending":
        raise AppError(409, "conflict", f"Recommendation already {rec.status}")
    rec.decided_at = datetime.now(timezone.utc)
    budget = None
    if approve:
        final = to_money(amount) if amount is not None else rec.proposed_amount
        existing = find_budget(db, user_id, rec.category_id, rec.month)
        rec.status = "approved"
        db.flush()
        if existing:
            budget = update_budget(db, user_id, existing.id, amount=final)
        else:
            budget = create_budget(db, user_id, rec.category_id, rec.month, final, notes="From JOCASTA recommendation")
        audit(db, user_id, "recommendation.approve", "budget_recommendation", rec.id)
    else:
        rec.status = "rejected"
        audit(db, user_id, "recommendation.reject", "budget_recommendation", rec.id)
    db.commit()
    return rec, budget


def all_categories_for_budget(db, user_id):
    return [c for c in list_categories(db, user_id) if c.kind != "income"]
