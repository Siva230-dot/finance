from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.core.rate_limit import limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.services.audit import audit

router = APIRouter(prefix="/auth", tags=["auth"])


def _token(user: User) -> TokenOut:
    token, expires = create_access_token(str(user.id), user.token_version)
    return TokenOut(access_token=token, expires_in=expires, user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenOut, status_code=201)
@limiter.limit("10/minute")
def register(request: Request, body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise AppError(409, "email_taken", "An account with this email already exists")
    user = User(email=email, full_name=body.full_name, password_hash=hash_password(body.password), currency=body.currency)
    db.add(user)
    db.flush()
    audit(db, user.id, "auth.register", "user", user.id)
    db.commit()
    db.refresh(user)
    return _token(user)


@router.post("/login", response_model=TokenOut)
@limiter.limit("10/minute")
def login(request: Request, body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash) or not user.is_active:
        raise AppError(401, "invalid_credentials", "Incorrect email or password")
    audit(db, user.id, "auth.login", "user", user.id)
    db.commit()
    return _token(user)


@router.post("/logout", status_code=204)
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Stateless JWT: bumping token_version revokes every token issued to this user.
    user.token_version += 1
    audit(db, user.id, "auth.logout", "user", user.id)
    db.commit()
