import re
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.models import Budget, Category, Transaction, User
from app.schemas import CategoryIn, CategoryOut
from app.services.audit import audit
from app.services.categories import list_categories

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list_categories(db, user.id)


@router.post("", response_model=CategoryOut, status_code=201)
def create(body: CategoryIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    name = body.name.strip()
    clash = db.scalar(select(Category).where(func.lower(Category.name) == name.lower(), or_(Category.user_id.is_(None), Category.user_id == user.id)))
    if clash:
        raise AppError(409, "conflict", "A category with this name already exists")
    slug = "custom-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    cat = Category(user_id=user.id, name=name, slug=slug[:60], kind=body.kind, color=body.color or "#8A8577", is_system=False)
    db.add(cat)
    db.flush()
    audit(db, user.id, "category.create", "category", cat.id)
    db.commit()
    return cat


@router.delete("/{category_id}", status_code=204)
def delete(category_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cat = db.scalar(select(Category).where(Category.id == category_id, Category.user_id == user.id))
    if not cat:
        raise AppError(404, "not_found", "Custom category not found")
    used = db.scalar(select(func.count()).select_from(Transaction).where(Transaction.category_id == cat.id)) or 0
    used += db.scalar(select(func.count()).select_from(Budget).where(Budget.category_id == cat.id)) or 0
    if used:
        raise AppError(409, "in_use", "This category is used by transactions or budgets. Recategorize them first.")
    db.delete(cat)
    audit(db, user.id, "category.delete", "category", category_id)
    db.commit()
