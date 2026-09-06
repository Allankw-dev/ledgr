from datetime import datetime

from pydantic import BaseModel


class AuditLogEntry(BaseModel):
    id: str
    actor_name: str
    action: str
    entity_type: str
    entity_id: str
    metadata: dict | None
    created_at: datetime
