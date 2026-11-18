import uuid

from sqlalchemy.orm import Session

from app.models import AuditLog


def audit(db: Session, user_id: uuid.UUID, action: str, entity_type: str, entity_id=None, actor: str = "user", details: dict | None = None) -> None:
    """Append an audit entry (committed with the caller's transaction)."""
    db.add(
        AuditLog(
            user_id=user_id,
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            details=details,
        )
    )
