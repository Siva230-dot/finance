import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas import BudgetIn, BudgetUpdateIn, RecommendationOut
from app.services import budgets as svc
from app.services.money import add_months, month_start

router = APIRouter(prefix="/budgets", tags=["budgets"])


class DecisionIn(BaseModel):
    approve: bool
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)


class GenerateIn(BaseModel):
    month: date | None = None
    category_id: uuid.UUID | None = None


@router.get("")
def list_budgets(month: date | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = month_start(month or date.today())
    items = svc.budget_status(db, user.id, m)
    prev = svc.budget_status(db, user.id, add_months(m, -1))
    total = sum((Decimal(b["amount"]) for b in items), Decimal("0"))
    spent = sum((Decimal(b["spent"]) for b in items), Decimal("0"))
    return {"month": m.isoformat(), "items": items, "previous_month": prev,
            "totals": {"budgeted": str(total), "spent": str(spent), "remaining": str(total - spent),
                       "utilization": str((spent / total * 100).quantize(Decimal("0.1"))) if total else "0.0"}}


@router.post("", status_code=201)
def create(body: BudgetIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = svc.create_budget(db, user.id, body.category_id, body.month, body.amount, body.notes)
    return next(x for x in svc.budget_status(db, user.id, b.month) if x["id"] == str(b.id))


@router.post("/copy-previous", status_code=201)
def copy_previous(month: date | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = month_start(month or date.today())
    created = 0
    for b in svc.budget_status(db, user.id, add_months(m, -1)):
        if not svc.find_budget(db, user.id, uuid.UUID(b["category"]["id"]), m):
            svc.create_budget(db, user.id, uuid.UUID(b["category"]["id"]), m, Decimal(b["amount"]), b["notes"])
            created += 1
    return {"created": created}


@router.patch("/{budget_id}")
def update(budget_id: uuid.UUID, body: BudgetUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = svc.update_budget(db, user.id, budget_id, body.amount, body.notes)
    return next(x for x in svc.budget_status(db, user.id, b.month) if x["id"] == str(b.id))


@router.delete("/{budget_id}", status_code=204)
def delete(budget_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc.delete_budget(db, user.id, budget_id)


@router.get("/recommendations", response_model=list[RecommendationOut])
def recommendations(month: date | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_recommendations(db, user.id, month)


@router.post("/recommendations/generate", response_model=list[RecommendationOut])
def generate(body: GenerateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    month = body.month or add_months(month_start(date.today()), 1)
    return svc.generate_recommendations(db, user.id, month, body.category_id)


@router.post("/recommendations/{rec_id}/decision")
def decide(rec_id: uuid.UUID, body: DecisionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rec, budget = svc.decide_recommendation(db, user.id, rec_id, body.approve, body.amount)
    return {"status": rec.status, "budget_id": str(budget.id) if budget else None}
