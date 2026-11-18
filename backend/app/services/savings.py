"""Savings goals and deterministic progress maths."""
import uuid
from datetime import date, datetime, timezone
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import SavingsContribution, SavingsGoal
from app.services.audit import audit
from app.services.money import ZERO, to_money


def months_between(start: date, end: date) -> int:
    """Whole months remaining, counting a partial month as one (minimum 1 if the date is in the future)."""
    if end <= start:
        return 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day > start.day:
        months += 1
    return max(months, 1)


def goal_progress(target: Decimal, current: Decimal, target_date: date | None, today: date | None = None) -> dict:
    today = today or date.today()
    target, current = to_money(target), to_money(current)
    remaining = max(target - current, ZERO)
    progress = (min(current / target, Decimal("1")) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) if target > 0 else ZERO
    months = months_between(today, target_date) if target_date else None
    required = None
    if target_date and remaining > 0:
        required = (remaining / months).quantize(Decimal("0.01"), rounding=ROUND_CEILING) if months else remaining
    on_track = None
    if target_date:
        on_track = remaining == 0 or (months or 0) > 0
    return {
        "remaining_amount": remaining,
        "progress_percent": progress,
        "months_remaining": months,
        "required_monthly": required,
        "on_track": on_track,
    }


def _q(user_id):
    return select(SavingsGoal).where(SavingsGoal.user_id == user_id, SavingsGoal.deleted_at.is_(None))


def get_goal(db: Session, user_id: uuid.UUID, goal_id: uuid.UUID) -> SavingsGoal:
    g = db.scalar(_q(user_id).where(SavingsGoal.id == goal_id))
    if not g:
        raise AppError(404, "not_found", "Savings goal not found")
    return g


def list_goals(db: Session, user_id: uuid.UUID, include_archived: bool = True) -> list[SavingsGoal]:
    q = _q(user_id)
    if not include_archived:
        q = q.where(SavingsGoal.status != "archived")
    return list(db.scalars(q.order_by(SavingsGoal.created_at.desc())))


def enrich(goal: SavingsGoal, with_contributions: bool = True) -> dict:
    p = goal_progress(goal.target_amount, goal.current_amount, goal.target_date)
    data = {
        "id": goal.id, "name": goal.name, "target_amount": goal.target_amount, "current_amount": goal.current_amount,
        "target_date": goal.target_date, "status": goal.status, "notes": goal.notes, "created_at": goal.created_at, **p,
        "contributions": list(goal.contributions[:50]) if with_contributions else [],
    }
    return data


def goals_with_progress(db: Session, user_id: uuid.UUID) -> list[dict]:
    out = []
    for g in list_goals(db, user_id, include_archived=False):
        p = goal_progress(g.target_amount, g.current_amount, g.target_date)
        out.append(
            {"id": str(g.id), "name": g.name, "target_amount": str(g.target_amount), "current_amount": str(g.current_amount),
             "target_date": g.target_date.isoformat() if g.target_date else None, "status": g.status,
             "remaining_amount": str(p["remaining_amount"]), "progress_percent": str(p["progress_percent"]),
             "months_remaining": p["months_remaining"],
             "required_monthly": str(p["required_monthly"]) if p["required_monthly"] is not None else None}
        )
    return out


def create_goal(db: Session, user_id: uuid.UUID, name: str, target_amount, current_amount=0, target_date=None, notes=None, actor="user") -> SavingsGoal:
    target, current = to_money(target_amount), to_money(current_amount or 0)
    if target <= 0:
        raise AppError(422, "validation_error", "Target amount must be greater than zero")
    if current < 0:
        raise AppError(422, "validation_error", "Current savings cannot be negative")
    if target_date and target_date <= date.today():
        raise AppError(422, "validation_error", "Target date must be in the future")
    g = SavingsGoal(user_id=user_id, name=name.strip(), target_amount=target, current_amount=current, target_date=target_date, notes=notes,
                    status="completed" if current >= target else "active")
    db.add(g)
    db.flush()
    if current > 0:
        db.add(SavingsContribution(goal_id=g.id, user_id=user_id, amount=current, contribution_date=date.today(), note="Opening balance"))
    audit(db, user_id, "goal.create", "savings_goal", g.id, actor)
    db.commit()
    db.refresh(g)
    return g


def update_goal(db: Session, user_id: uuid.UUID, goal_id: uuid.UUID, changes: dict, actor="user") -> SavingsGoal:
    g = get_goal(db, user_id, goal_id)
    if changes.get("name"):
        g.name = changes["name"].strip()
    if changes.get("target_amount") is not None:
        t = to_money(changes["target_amount"])
        if t <= 0:
            raise AppError(422, "validation_error", "Target amount must be greater than zero")
        g.target_amount = t
    if "target_date" in changes and changes["target_date"] is not None:
        g.target_date = changes["target_date"]
    if changes.get("notes") is not None:
        g.notes = changes["notes"]
    if changes.get("status"):
        g.status = changes["status"]
    elif g.status == "completed" and g.current_amount < g.target_amount:
        g.status = "active"
    elif g.status == "active" and g.current_amount >= g.target_amount:
        g.status = "completed"
    audit(db, user_id, "goal.update", "savings_goal", g.id, actor)
    db.commit()
    db.refresh(g)
    return g


def delete_goal(db: Session, user_id: uuid.UUID, goal_id: uuid.UUID, actor="user") -> SavingsGoal:
    g = get_goal(db, user_id, goal_id)
    g.deleted_at = datetime.now(timezone.utc)
    audit(db, user_id, "goal.delete", "savings_goal", g.id, actor)
    db.commit()
    return g


def add_contribution(db: Session, user_id: uuid.UUID, goal_id: uuid.UUID, amount, contribution_date=None, note=None, actor="user") -> SavingsGoal:
    g = get_goal(db, user_id, goal_id)
    amt = to_money(amount)
    if amt == 0:
        raise AppError(422, "validation_error", "Contribution cannot be zero")
    if g.current_amount + amt < 0:
        raise AppError(422, "validation_error", "Withdrawal exceeds the saved amount")
    db.add(SavingsContribution(goal_id=g.id, user_id=user_id, amount=amt, contribution_date=contribution_date or date.today(), note=note))
    g.current_amount = g.current_amount + amt
    if g.current_amount >= g.target_amount and g.status == "active":
        g.status = "completed"
    elif g.current_amount < g.target_amount and g.status == "completed":
        g.status = "active"
    audit(db, user_id, "goal.contribution", "savings_goal", g.id, actor)
    db.commit()
    db.refresh(g)
    return g


def serialize_goal(g: SavingsGoal) -> dict:
    p = goal_progress(g.target_amount, g.current_amount, g.target_date)
    return {
        "id": str(g.id), "name": g.name, "target_amount": str(g.target_amount), "current_amount": str(g.current_amount),
        "target_date": g.target_date.isoformat() if g.target_date else None, "status": g.status,
        "remaining_amount": str(p["remaining_amount"]), "progress_percent": str(p["progress_percent"]),
        "months_remaining": p["months_remaining"],
        "required_monthly": str(p["required_monthly"]) if p["required_monthly"] is not None else None,
    }
