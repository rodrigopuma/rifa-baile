from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditLog


def log(db: Session, action: str, *, actor_type: str = "system", actor_id: str = "",
        entity_type: str = "", entity_id: Any = "", details: dict[str, Any] | None = None) -> None:
    db.add(AuditLog(actor_type=actor_type, actor_id=str(actor_id or ""), action=action,
                    entity_type=entity_type, entity_id=str(entity_id or ""), details=details or {}))
