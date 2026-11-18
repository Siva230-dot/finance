import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.models import User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise AppError(401, "unauthorized", "Authentication required")
    payload = decode_access_token(creds.credentials)
    if not payload:
        raise AppError(401, "unauthorized", "Invalid or expired token")
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise AppError(401, "unauthorized", "Invalid token")
    user = db.get(User, user_id)
    if not user or not user.is_active or user.token_version != payload.get("tv"):
        raise AppError(401, "unauthorized", "Session is no longer valid")
    return user
