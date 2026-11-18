import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas import TransactionIn, TransactionOut, TransactionPage, TransactionUpdateIn
from app.services import transactions as svc

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _filters(
    search: str | None = Query(None, max_length=100),
    category_id: uuid.UUID | None = None,
    type: Literal["income", "expense"] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    min_amount: Decimal | None = Query(None, ge=0),
    max_amount: Decimal | None = Query(None, ge=0),
    sort: Literal["date", "amount", "description", "created"] = "date",
    order: Literal["asc", "desc"] = "desc",
):
    return dict(search=search, category_id=category_id, tx_type=type, start=start_date, end=end_date,
                min_amount=min_amount, max_amount=max_amount, sort=sort, order=order)


@router.get("", response_model=TransactionPage)
def list_transactions(f: dict = Depends(_filters), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200),
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items, total = svc.query_transactions(db, user.id, page=page, page_size=page_size, **f)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/export")
def export(f: dict = Depends(_filters), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items, _ = svc.query_transactions(db, user.id, page_size=500, **f)
    rows = list(items)
    page = 2
    while len(rows) == (page - 1) * 500:
        more, _ = svc.query_transactions(db, user.id, page=page, page_size=500, **f)
        if not more:
            break
        rows.extend(more)
        page += 1
    return Response(svc.export_csv(rows), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="transactions.csv"'})


@router.get("/duplicates")
def duplicates(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    groups = svc.find_duplicates(db, user.id)
    return {"groups": [[svc.serialize_tx(t) for t in g] for g in groups]}


@router.post("/recurring/run")
def run_recurring(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"created": svc.run_recurring(db, user.id)}


@router.post("", response_model=TransactionOut, status_code=201)
def create(body: TransactionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.create_transaction(
        db, user.id, description=body.description, amount=body.amount, tx_type=body.type, transaction_date=body.transaction_date,
        category_id=body.category_id, payment_method=body.payment_method, notes=body.notes,
        is_recurring=body.is_recurring, recurrence_interval=body.recurrence_interval,
    )


@router.get("/{tx_id}", response_model=TransactionOut)
def get(tx_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.get_transaction(db, user.id, tx_id)


@router.patch("/{tx_id}", response_model=TransactionOut)
def update(tx_id: uuid.UUID, body: TransactionUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.update_transaction(db, user.id, tx_id, body.model_dump(exclude_unset=True))


@router.delete("/{tx_id}", status_code=204)
def delete(tx_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc.delete_transaction(db, user.id, tx_id)
