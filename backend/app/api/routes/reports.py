from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import FinancialReport, User
from app.services import reports as svc

router = APIRouter(prefix="/reports", tags=["reports"])


def _period(report_type: str, month: date | None, year: int | None) -> date:
    if report_type == "annual":
        return date(year or date.today().year, 1, 1)
    return month or date.today()


@router.get("/{report_type}")
def get_report(report_type: Literal["monthly", "annual"], month: date | None = None, year: int | None = Query(None, ge=2000, le=2100),
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.build_report(db, user.id, report_type, _period(report_type, month, year), save=False)


@router.get("/{report_type}/download")
def download(report_type: Literal["monthly", "annual"], format: Literal["pdf", "csv"] = "pdf", month: date | None = None,
             year: int | None = Query(None, ge=2000, le=2100), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    payload = svc.build_report(db, user.id, report_type, _period(report_type, month, year), save=True)
    stem = f"financemate-{report_type}-{payload['period_start'][:7 if report_type == 'monthly' else 4]}"
    if format == "csv":
        return Response(svc.render_csv(payload), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{stem}.csv"'})
    pdf = svc.render_pdf(payload, user.full_name, user.currency)
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{stem}.pdf"'})


@router.get("")
def history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(FinancialReport).where(FinancialReport.user_id == user.id).order_by(FinancialReport.created_at.desc()).limit(20))
    return [{"id": str(r.id), "report_type": r.report_type, "period_start": r.period_start.isoformat(), "period_end": r.period_end.isoformat(),
             "created_at": r.created_at.isoformat()} for r in rows]
