from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.control_plane.repositories import processed_worker_updates, tasks, tenants
from app.shared.state import (
    StateTransitionError,
    TaskStatus,
    apply_task_progress,
    apply_terminal_task_to_tenant,
)
from app.shared.time import format_utc_millis, utc_now


def apply_worker_progress(
    session: Session,
    *,
    idempotency_key: str,
    task_id: UUID,
    status: str,
    occurred_at: str,
) -> bool:
    try:
        incoming_status = TaskStatus(status)
    except ValueError:
        return False

    if not idempotency_key or not occurred_at:
        return False

    try:
        datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
    except ValueError:
        return False

    if session.in_transaction():
        transaction = session.begin_nested()
    else:
        transaction = session.begin()

    with transaction:
        if processed_worker_updates.has_processed_worker_update(
            session,
            idempotency_key=idempotency_key,
        ):
            return False

        task = tasks.get_task(session, task_id)
        if task is None:
            return False

        try:
            transition = apply_task_progress(task.status, incoming_status)
        except StateTransitionError:
            return False

        if not transition.changed:
            processed_worker_updates.add_processed_worker_update(
                session,
                idempotency_key=idempotency_key,
                task_id=task.id,
            )
            return False

        task.status = incoming_status
        task.updated_at = utc_now()

        if transition.terminal:
            tenant = tenants.get_tenant(session, task.tenant_id)
            if tenant is None:
                return False

            try:
                next_status = apply_terminal_task_to_tenant(
                    tenant.status,
                    task.type,
                    incoming_status,
                )
            except StateTransitionError:
                return False

            tenant.status = next_status
            tenant.version += 1
            tenant.updated_at = utc_now()

        processed_worker_updates.add_processed_worker_update(
            session,
            idempotency_key=idempotency_key,
            task_id=task.id,
        )
        return True


def parse_progress_payload(payload: dict[str, object]) -> tuple[str, UUID, str, str]:
    if not isinstance(payload, dict):
        raise ValueError("Progress payload must be a JSON object.")

    idempotency_key = payload.get("id")
    task_id = payload.get("task_id")
    status = payload.get("status")
    occurred_at = payload.get("occurred_at")

    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise ValueError("Progress payload is missing a stable idempotency key.")
    if not isinstance(task_id, str):
        raise ValueError("Progress payload is missing task_id.")
    if not isinstance(status, str) or not status:
        raise ValueError("Progress payload is missing status.")
    if not isinstance(occurred_at, str) or not occurred_at:
        raise ValueError("Progress payload is missing occurred_at.")

    try:
        parsed_task_id = UUID(task_id)
    except ValueError as exc:
        raise ValueError("Progress payload task_id is not a valid UUID.") from exc

    try:
        TaskStatus(status)
    except ValueError as exc:
        raise ValueError(f"Unsupported task status: {status}") from exc

    datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
    return idempotency_key, parsed_task_id, status, occurred_at


def serialize_progress_event(task_id: UUID, *, status: str, occurred_at: str) -> dict[str, str]:
    return {
        "id": format_utc_millis(utc_now()),
        "task_id": str(task_id),
        "status": status,
        "occurred_at": occurred_at,
    }
