import json

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.models import AuditLog, Budget, SavingsContribution, SavingsGoal, Transaction, User
from app.schemas import SUPPORTED_CURRENCIES, AccountDeleteIn, PasswordChangeIn, UserOut, UserUpdateIn
from app.services.audit import audit

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: UserUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for k, v in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(user, k, v)
    audit(db, user.id, "user.update", "user", user.id, details={"fields": list(body.model_dump(exclude_unset=True))})
    db.commit()
    db.refresh(user)
    return user


@router.get("/currencies")
def currencies():
    return {"currencies": SUPPORTED_CURRENCIES}


@router.post("/me/password")
def change_password(body: PasswordChangeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise AppError(400, "invalid_password", "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1  # sign out other sessions
    audit(db, user.id, "user.password_change", "user", user.id)
    db.commit()
    token, expires = create_access_token(str(user.id), user.token_version)
    return {"access_token": token, "token_type": "bearer", "expires_in": expires}


@router.get("/me/export")
def export_data(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    def rows(model, *order):
        return db.scalars(select(model).where(model.user_id == user.id).order_by(*order)).unique().all()

    data = {
        "profile": {"email": user.email, "full_name": user.full_name, "currency": user.currency, "created_at": user.created_at.isoformat()},
        "transactions": [
            {"id": str(t.id), "date": t.transaction_date.isoformat(), "description": t.description, "amount": str(t.amount), "type": t.type,
             "category": t.category.name, "payment_method": t.payment_method, "notes": t.notes, "deleted": t.deleted_at is not None}
            for t in rows(Transaction, Transaction.transaction_date)
        ],
        "budgets": [{"category": b.category.name, "month": b.month.isoformat(), "amount": str(b.amount), "deleted": b.deleted_at is not None}
                    for b in rows(Budget, Budget.month)],
        "savings_goals": [{"name": g.name, "target": str(g.target_amount), "current": str(g.current_amount),
                           "target_date": g.target_date.isoformat() if g.target_date else None, "status": g.status}
                          for g in rows(SavingsGoal, SavingsGoal.created_at)],
        "savings_contributions": [{"goal_id": str(c.goal_id), "amount": str(c.amount), "date": c.contribution_date.isoformat()}
                                  for c in rows(SavingsContribution, SavingsContribution.contribution_date)],
        "audit_log": [{"action": a.action, "entity": a.entity_type, "actor": a.actor, "at": a.created_at.isoformat()}
                      for a in rows(AuditLog, AuditLog.created_at)],
    }
    audit(db, user.id, "user.export", "user", user.id)
    db.commit()
    return Response(json.dumps(data, indent=2), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="financemate-export.json"'})


@router.delete("/me", status_code=204)
def delete_account(body: AccountDeleteIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.password, user.password_hash):
        raise AppError(400, "invalid_password", "Password is incorrect")
    # Hard delete: cascades remove every row owned by the user (privacy control).
    db.delete(user)
    db.commit()
