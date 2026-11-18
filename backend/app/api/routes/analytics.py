from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.models import User
from app.services import analytics as svc
from app.services.money import month_end, month_start

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
def overview(month: date | None = None, months: int = Query(6, ge=1, le=24), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.overview(db, user.id, month or date.today(), months)


@router.get("/summary")
def summary(start_date: date | None = None, end_date: date | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = start_date or month_start(date.today())
    e = end_date or month_end(s)
    if e < s:
        raise AppError(422, "validation_error", "end_date must be after start_date")
    return svc.period_summary(db, user.id, s, e)


@router.get("/categories")
def categories(start_date: date | None = None, end_date: date | None = None, type: Literal["income", "expense"] = "expense",
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = start_date or month_start(date.today())
    return svc.category_breakdown(db, user.id, s, end_date or month_end(s), type)


@router.get("/trends")
def trends(month: date | None = None, months: int = Query(12, ge=1, le=36), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = month or date.today()
    return {"monthly": svc.monthly_series(db, user.id, m, months), "daily": svc.daily_trend(db, user.id, month_start(m), month_end(m)),
            "average_monthly_expense": str(svc.average_monthly_expense(db, user.id, m, min(months, 12)))}


@router.get("/comparison")
def comparison(month: date | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.month_over_month(db, user.id, month or date.today())
