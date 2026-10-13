from uuid import UUID, uuid4

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
