from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.shared.models import OutboxEvent


def add_task_created_event(
    session: Session,
    *,
    task_id: UUID,
    occurred_at: str,
    task_payload: dict[str, Any],
) -> OutboxEvent:
    event = OutboxEvent(
        id=task_id,
        event_type="task.created",
        exchange="tenant-provisioning",
        routing_key="task.created",
        payload={
            "id": str(task_id),
            "event_type": "task.created",
            "occurred_at": occurred_at,
            "task": task_payload,
        },
    )
    session.add(event)
    session.flush()
    return event
