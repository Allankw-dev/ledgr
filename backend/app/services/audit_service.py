from sqlalchemy.orm import Session

from app.models.payment import AuditLog


def log_audit(
    db: Session,
    school_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    user_id: str | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    """Audit trails for a financial system should never silently fail —
    this runs in the same transaction as the action it's logging."""
    entry = AuditLog(
        school_id=school_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        log_metadata=metadata,
    )
    db.add(entry)
    return entry
