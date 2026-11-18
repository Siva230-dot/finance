"""Transaction domain logic shared by REST routes and JOCASTA tools. Every query is scoped by user_id."""
import csv
import hashlib
import io
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Category, Transaction
from app.services.audit import audit
from app.services.categories import category_by_slug, get_category, rule_categorize
from app.services.money import add_months, to_money

SORTABLE = {
    "date": Transaction.transaction_date,
    "amount": Transaction.amount,
    "description": Transaction.description,
    "created": Transaction.created_at,
}


def normalize_description(desc: str) -> str:
    d = re.sub(r"[^a-z0-9 ]+", " ", desc.lower())
    d = re.sub(r"\b\d{6,}\b", " ", d)  # strip long reference numbers
    return re.sub(r"\s+", " ", d).strip()


def dedupe_hash(tx_date: date, amount: Decimal, tx_type: str, description: str) -> str:
    key = f"{tx_date.isoformat()}|{to_money(amount)}|{tx_type}|{normalize_description(description)}"
    return hashlib.sha256(key.encode()).hexdigest()


def _base(user_id: uuid.UUID) -> Select:
    return select(Transaction).where(Transaction.user_id == user_id, Transaction.deleted_at.is_(None))


def get_transaction(db: Session, user_id: uuid.UUID, tx_id: uuid.UUID) -> Transaction:
    tx = db.scalar(_base(user_id).where(Transaction.id == tx_id))
    if not tx:
        raise AppError(404, "not_found", "Transaction not found")
    return tx


def _next_occurrence(d: date, interval: str | None) -> date | None:
    if interval == "weekly":
        return d + timedelta(days=7)
    if interval == "monthly":
        return add_months(d, 1)
    if interval == "yearly":
        return add_months(d, 12)
    return None


def create_transaction(
    db: Session,
    user_id: uuid.UUID,
    *,
    description: str,
    amount: Decimal,
    tx_type: str,
    transaction_date: date,
    category_id: uuid.UUID | None = None,
    payment_method: str | None = None,
    notes: str | None = None,
    is_recurring: bool = False,
    recurrence_interval: str | None = None,
    actor: str = "user",
    categorization_source: str | None = None,
    categorization_confidence: Decimal | None = None,
    import_batch_id: uuid.UUID | None = None,
    commit: bool = True,
) -> Transaction:
    amount = to_money(amount)
    if amount <= 0:
        raise AppError(422, "validation_error", "Amount must be greater than zero")
    if tx_type not in ("income", "expense"):
        raise AppError(422, "validation_error", "Type must be income or expense")
    if is_recurring and recurrence_interval not in ("weekly", "monthly", "yearly"):
        raise AppError(422, "validation_error", "Recurring transactions need an interval: weekly, monthly or yearly")
    if category_id:
        cat = get_category(db, user_id, category_id)
        source, conf = categorization_source or "user", categorization_confidence or Decimal("1.000")
    else:
        guess = rule_categorize(description, tx_type)
        slug = guess.slug if guess else ("income" if tx_type == "income" else "other")
        cat = category_by_slug(db, user_id, slug)
        source = guess.source if guess else "default"
        conf = guess.confidence if guess else Decimal("0.300")
    tx = Transaction(
        user_id=user_id,
        description=description.strip(),
        amount=amount,
        type=tx_type,
        category_id=cat.id,
        transaction_date=transaction_date,
        payment_method=payment_method,
        notes=notes,
        is_recurring=is_recurring,
        recurrence_interval=recurrence_interval if is_recurring else None,
        next_occurrence=_next_occurrence(transaction_date, recurrence_interval) if is_recurring else None,
        categorization_source=source,
        categorization_confidence=conf,
        dedupe_hash=dedupe_hash(transaction_date, amount, tx_type, description),
        import_batch_id=import_batch_id,
    )
    tx.category = cat
    db.add(tx)
    db.flush()
    audit(db, user_id, "transaction.create", "transaction", tx.id, actor)
    if commit:
        db.commit()
        db.refresh(tx)
    return tx


def update_transaction(db: Session, user_id: uuid.UUID, tx_id: uuid.UUID, changes: dict, actor: str = "user") -> Transaction:
    tx = get_transaction(db, user_id, tx_id)
    changed: list[str] = []
    for field in ("description", "amount", "type", "transaction_date", "payment_method", "notes", "is_recurring", "recurrence_interval"):
        if field in changes and changes[field] is not None:
            value = to_money(changes[field]) if field == "amount" else changes[field]
            if field == "amount" and value <= 0:
                raise AppError(422, "validation_error", "Amount must be greater than zero")
            setattr(tx, field, value)
            changed.append(field)
    if changes.get("category_id"):
        cat = get_category(db, user_id, changes["category_id"])
        tx.category_id, tx.category = cat.id, cat
        tx.categorization_source, tx.categorization_confidence = "user", Decimal("1.000")
        changed.append("category")
    if tx.is_recurring:
        if tx.recurrence_interval not in ("weekly", "monthly", "yearly"):
            raise AppError(422, "validation_error", "Recurring transactions need an interval")
        tx.next_occurrence = tx.next_occurrence or _next_occurrence(tx.transaction_date, tx.recurrence_interval)
    else:
        tx.recurrence_interval, tx.next_occurrence = None, None
    tx.dedupe_hash = dedupe_hash(tx.transaction_date, tx.amount, tx.type, tx.description)
    audit(db, user_id, "transaction.update", "transaction", tx.id, actor, {"fields": changed})
    db.commit()
    db.refresh(tx)
    return tx


def delete_transaction(db: Session, user_id: uuid.UUID, tx_id: uuid.UUID, actor: str = "user") -> Transaction:
    """Soft delete: the row is retained for audit history but hidden from every query."""
    tx = get_transaction(db, user_id, tx_id)
    tx.deleted_at = datetime.now(timezone.utc)
    audit(db, user_id, "transaction.delete", "transaction", tx.id, actor, {"date": tx.transaction_date.isoformat()})
    db.commit()
    return tx


def query_transactions(
    db: Session,
    user_id: uuid.UUID,
    *,
    search: str | None = None,
    category_id: uuid.UUID | None = None,
    category_ids: list[uuid.UUID] | None = None,
    tx_type: str | None = None,
    start: date | None = None,
    end: date | None = None,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
    sort: str = "date",
    order: str = "desc",
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Transaction], int]:
    q = _base(user_id)
    if search:
        like = f"%{search.strip()}%"
        q = q.join(Category, Category.id == Transaction.category_id).where(
            or_(Transaction.description.ilike(like), Transaction.notes.ilike(like), Category.name.ilike(like))
        )
    if category_id:
        q = q.where(Transaction.category_id == category_id)
    if category_ids:
        q = q.where(Transaction.category_id.in_(category_ids))
    if tx_type in ("income", "expense"):
        q = q.where(Transaction.type == tx_type)
    if start:
        q = q.where(Transaction.transaction_date >= start)
    if end:
        q = q.where(Transaction.transaction_date <= end)
    if min_amount is not None:
        q = q.where(Transaction.amount >= min_amount)
    if max_amount is not None:
        q = q.where(Transaction.amount <= max_amount)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    col = SORTABLE.get(sort, Transaction.transaction_date)
    q = q.order_by(col.asc() if order == "asc" else col.desc(), Transaction.created_at.desc())
    page_size = max(1, min(page_size, 500))
    q = q.offset((max(page, 1) - 1) * page_size).limit(page_size)
    return list(db.scalars(q).unique()), total


def find_duplicates(db: Session, user_id: uuid.UUID) -> list[list[Transaction]]:
    dup_hashes = db.scalars(
        select(Transaction.dedupe_hash)
        .where(Transaction.user_id == user_id, Transaction.deleted_at.is_(None))
        .group_by(Transaction.dedupe_hash)
        .having(func.count() > 1)
    ).all()
    groups = []
    for h in dup_hashes:
        groups.append(list(db.scalars(_base(user_id).where(Transaction.dedupe_hash == h).order_by(Transaction.created_at)).unique()))
    return groups


def existing_hashes(db: Session, user_id: uuid.UUID, hashes: list[str]) -> set[str]:
    if not hashes:
        return set()
    return set(
        db.scalars(
            select(Transaction.dedupe_hash).where(
                Transaction.user_id == user_id, Transaction.deleted_at.is_(None), Transaction.dedupe_hash.in_(hashes)
            )
        )
    )


def run_recurring(db: Session, user_id: uuid.UUID, today: date | None = None) -> int:
    """Materialise due occurrences of recurring templates up to today (idempotent)."""
    today = today or date.today()
    templates = db.scalars(
        _base(user_id).where(Transaction.is_recurring.is_(True), Transaction.next_occurrence <= today)
    ).unique().all()
    created = 0
    for t in templates:
        guard = 0
        while t.next_occurrence and t.next_occurrence <= today and guard < 60:
            db.add(
                Transaction(
                    user_id=user_id, description=t.description, amount=t.amount, type=t.type, category_id=t.category_id,
                    transaction_date=t.next_occurrence, payment_method=t.payment_method, notes=t.notes,
                    recurring_parent_id=t.id, categorization_source=t.categorization_source,
                    categorization_confidence=t.categorization_confidence,
                    dedupe_hash=dedupe_hash(t.next_occurrence, t.amount, t.type, t.description),
                )
            )
            t.next_occurrence = _next_occurrence(t.next_occurrence, t.recurrence_interval)
            created += 1
            guard += 1
    if created:
        audit(db, user_id, "transaction.recurring_run", "transaction", None, "system", {"created": created})
    db.commit()
    return created


def export_csv(transactions: list[Transaction]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "date", "description", "type", "category", "amount", "payment_method", "notes"])
    for t in transactions:
        w.writerow([t.id, t.transaction_date.isoformat(), t.description, t.type, t.category.name, f"{t.amount}", t.payment_method or "", t.notes or ""])
    return buf.getvalue()


def serialize_tx(t: Transaction) -> dict:
    return {
        "id": str(t.id),
        "description": t.description,
        "amount": str(t.amount),
        "type": t.type,
        "category": t.category.name,
        "category_id": str(t.category_id),
        "date": t.transaction_date.isoformat(),
        "payment_method": t.payment_method,
        "notes": t.notes,
        "is_recurring": t.is_recurring,
        "categorization_source": t.categorization_source,
        "confidence": str(t.categorization_confidence) if t.categorization_confidence is not None else None,
    }
