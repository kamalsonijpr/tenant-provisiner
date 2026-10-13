from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.shared.models import ProcessedWorkerUpdate


def has_processed_worker_update(session: Session, *, idempotency_key: str) -> bool:
    return session.get(ProcessedWorkerUpdate, idempotency_key) is not None


def add_processed_worker_update(
    session: Session,
    *,
    idempotency_key: str,
    task_id: UUID,
) -> ProcessedWorkerUpdate:
    row = ProcessedWorkerUpdate(idempotency_key=idempotency_key, task_id=task_id)
    session.add(row)
    session.flush()
    return row


def get_processed_worker_update(
    session: Session,
    *,
    idempotency_key: str,
) -> ProcessedWorkerUpdate | None:
    return session.scalar(
        select(ProcessedWorkerUpdate).where(
            ProcessedWorkerUpdate.idempotency_key == idempotency_key,
        )
    )
