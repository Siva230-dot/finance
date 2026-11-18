"""Deterministic execution of user-confirmed actions. No LLM is involved at this stage."""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import PendingConfirmation, User
from app.services import budgets as budget_svc, savings as savings_svc, transactions as tx_svc

ACTOR = "jocasta"


def execute_action(db: Session, user: User, action: str, payload: dict, ctx=None) -> dict:
    uid = user.id
    if action == "create_transaction":
        t = tx_svc.create_transaction(
            db, uid, description=payload["description"], amount=Decimal(payload["amount"]), tx_type=payload["type"],
            transaction_date=date.fromisoformat(payload["transaction_date"]), category_id=uuid.UUID(payload["category_id"]),
            payment_method=payload.get("payment_method"), notes=payload.get("notes"), actor=ACTOR,
            categorization_source="user", categorization_confidence=Decimal("1.000"),
        )
        return {"type": "transaction_result", "operation": "created", "record": tx_svc.serialize_tx(t)}
    if action == "update_transaction":
        changes = dict(payload["changes"])
        if "category_id" in changes:
            changes["category_id"] = uuid.UUID(changes["category_id"])
        if "transaction_date" in changes:
            changes["transaction_date"] = date.fromisoformat(changes["transaction_date"])
        t = tx_svc.update_transaction(db, uid, uuid.UUID(payload["transaction_id"]), changes, actor=ACTOR)
        return {"type": "transaction_result", "operation": "updated", "record": tx_svc.serialize_tx(t)}
    if action == "delete_transaction":
        t = tx_svc.delete_transaction(db, uid, uuid.UUID(payload["transaction_id"]), actor=ACTOR)
        return {"type": "transaction_result", "operation": "deleted", "record": tx_svc.serialize_tx(t)}
    if action == "create_budget":
        b = budget_svc.create_budget(db, uid, uuid.UUID(payload["category_id"]), date.fromisoformat(payload["month"]), Decimal(payload["amount"]), actor=ACTOR)
        return {"type": "budget_result", "operation": "created", "record": _budget(b)}
    if action == "update_budget":
        b = budget_svc.update_budget(db, uid, uuid.UUID(payload["budget_id"]), amount=Decimal(payload["amount"]), actor=ACTOR)
        return {"type": "budget_result", "operation": "updated", "record": _budget(b)}
    if action == "delete_budget":
        b = budget_svc.delete_budget(db, uid, uuid.UUID(payload["budget_id"]), actor=ACTOR)
        return {"type": "budget_result", "operation": "deleted", "record": _budget(b)}
    if action == "create_savings_goal":
        g = savings_svc.create_goal(db, uid, payload["name"], Decimal(payload["target_amount"]), Decimal(payload.get("current_amount") or "0"),
                                    date.fromisoformat(payload["target_date"]) if payload.get("target_date") else None, actor=ACTOR)
        return {"type": "savings_result", "operation": "created", "record": savings_svc.serialize_goal(g)}
    if action == "update_savings_goal":
        changes = dict(payload["changes"])
        if changes.get("target_date"):
            changes["target_date"] = date.fromisoformat(changes["target_date"])
        if changes.get("target_amount"):
            changes["target_amount"] = Decimal(changes["target_amount"])
        g = savings_svc.update_goal(db, uid, uuid.UUID(payload["goal_id"]), changes, actor=ACTOR)
        return {"type": "savings_result", "operation": "updated", "record": savings_svc.serialize_goal(g)}
    if action == "delete_savings_goal":
        g = savings_svc.delete_goal(db, uid, uuid.UUID(payload["goal_id"]), actor=ACTOR)
        return {"type": "savings_result", "operation": "deleted", "record": savings_svc.serialize_goal(g)}
    if action == "record_savings_contribution":
        g = savings_svc.add_contribution(db, uid, uuid.UUID(payload["goal_id"]), Decimal(payload["amount"]),
                                         date.fromisoformat(payload["date"]) if payload.get("date") else None, payload.get("note"), actor=ACTOR)
        return {"type": "savings_result", "operation": "contribution", "record": savings_svc.serialize_goal(g), "amount": payload["amount"]}
    raise AppError(400, "unknown_action", "Unsupported action")


def _budget(b) -> dict:
    return {"id": str(b.id), "category": b.category.name, "month": b.month.isoformat(), "amount": str(b.amount)}


def get_pending(db: Session, user_id: uuid.UUID, confirmation_id: uuid.UUID) -> PendingConfirmation:
    pc = db.scalar(select(PendingConfirmation).where(PendingConfirmation.id == confirmation_id, PendingConfirmation.user_id == user_id))
    if not pc:
        raise AppError(404, "not_found", "Confirmation not found")
    return pc


def latest_pending(db: Session, user_id: uuid.UUID, conversation_id: uuid.UUID | None) -> PendingConfirmation | None:
    if conversation_id is None:
        return None
    pcs = db.scalars(
        select(PendingConfirmation)
        .where(PendingConfirmation.user_id == user_id, PendingConfirmation.conversation_id == conversation_id, PendingConfirmation.status == "pending")
        .order_by(PendingConfirmation.created_at.desc())
    ).all()
    now = datetime.now(timezone.utc)
    live = []
    for pc in pcs:
        if pc.expires_at < now:
            pc.status = "expired"
        else:
            live.append(pc)
    db.commit()
    return live[0] if live else None


def pending_in_conversation(db: Session, user_id: uuid.UUID, conversation_id: uuid.UUID) -> list[PendingConfirmation]:
    latest_pending(db, user_id, conversation_id)  # expire stale ones
    return list(db.scalars(
        select(PendingConfirmation)
        .where(PendingConfirmation.user_id == user_id, PendingConfirmation.conversation_id == conversation_id, PendingConfirmation.status == "pending")
        .order_by(PendingConfirmation.created_at)
    ))


def confirm(db: Session, user: User, confirmation_id: uuid.UUID) -> tuple[PendingConfirmation, dict]:
    pc = get_pending(db, user.id, confirmation_id)
    if pc.status != "pending":
        raise AppError(409, "conflict", f"This action was already {pc.status}.")
    if pc.expires_at < datetime.now(timezone.utc):
        pc.status = "expired"
        db.commit()
        raise AppError(410, "expired", "This confirmation has expired. Please ask JOCASTA again.")
    # Claim it first so a double click cannot run the action twice.
    pc.status = "confirmed"
    pc.resolved_at = datetime.now(timezone.utc)
    db.commit()
    try:
        result = execute_action(db, user, pc.action, pc.payload)
    except AppError as exc:
        db.rollback()
        pc = get_pending(db, user.id, confirmation_id)
        pc.status, pc.result = "failed", {"error": exc.message}
        db.commit()
        raise
    pc.result = result
    db.commit()
    return pc, result


def cancel(db: Session, user_id: uuid.UUID, confirmation_id: uuid.UUID) -> PendingConfirmation:
    pc = get_pending(db, user_id, confirmation_id)
    if pc.status != "pending":
        raise AppError(409, "conflict", f"This action was already {pc.status}.")
    pc.status, pc.resolved_at = "cancelled", datetime.now(timezone.utc)
    db.commit()
    return pc


def describe_result(result: dict, currency: str) -> str:
    r, op = result.get("record", {}), result.get("operation")
    kind = result.get("type")
    if kind == "transaction_result":
        base = f"{r.get('description')} — {currency} {r.get('amount')} ({r.get('category')}, {r.get('date')})"
        return {"created": f"Done. I've added the transaction: {base}.", "updated": f"Done. The transaction is updated: {base}.",
                "deleted": f"Done. I've deleted the transaction: {base}."}.get(op, "Done.")
    if kind == "budget_result":
        base = f"{r.get('category')} budget for {r.get('month', '')[:7]} at {currency} {r.get('amount')}"
        return {"created": f"Done. Your {base} is set.", "updated": f"Done. Your {base} is updated.", "deleted": f"Done. I've removed the {base}."}.get(op, "Done.")
    if kind == "savings_result":
        if op == "contribution":
            return f"Done. Recorded {currency} {result.get('amount')} toward {r.get('name')}. You're now at {r.get('progress_percent')}% ({currency} {r.get('remaining_amount')} to go)."
        base = f"'{r.get('name')}' (target {currency} {r.get('target_amount')})"
        return {"created": f"Done. Your savings goal {base} is created.", "updated": f"Done. Savings goal {base} is updated.",
                "deleted": f"Done. I've deleted the savings goal {base}."}.get(op, "Done.")
    return "Done."
