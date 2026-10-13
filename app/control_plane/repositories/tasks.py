from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.shared.models import Task
from app.shared.state import TaskStatus, TaskType


def add_task(
    session: Session,
    *,
    tenant_id: UUID,
    task_type: TaskType,
) -> Task:
    task = Task(
        id=uuid4(),
        type=task_type,
        tenant_id=tenant_id,
        status=TaskStatus.ACCEPTED,
    )
    session.add(task)
    session.flush()
    return task


def get_task(session: Session, task_id: UUID) -> Task | None:
    return session.get(Task, task_id)


def list_tasks(
    session: Session,
    *,
    offset: int,
    limit: int,
    tenant_id: UUID | None,
    status: TaskStatus | None,
    task_type: TaskType | None,
) -> list[Task]:
    query = select(Task).order_by(Task.created_at, Task.id)
    if tenant_id is not None:
        query = query.where(Task.tenant_id == tenant_id)
    if status is not None:
        query = query.where(Task.status == status)
    if task_type is not None:
        query = query.where(Task.type == task_type)
    return list(session.scalars(query.offset(offset).limit(limit + 1)))
