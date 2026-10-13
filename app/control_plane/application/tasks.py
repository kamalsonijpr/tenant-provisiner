from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.control_plane.api.errors import TaskNotFoundError
from app.control_plane.repositories import tasks as tasks_repository
from app.shared.models import Task
from app.shared.state import TaskStatus, TaskType


@dataclass(frozen=True)
class TaskPage:
    items: list[Task]
    next_cursor: str | None


def list_tasks(
    session: Session,
    *,
    limit: int,
    cursor: str | None,
    tenant_id: UUID | None,
    status: TaskStatus | None,
    task_type: TaskType | None,
) -> TaskPage:
    offset = _cursor_offset(cursor)
    rows = tasks_repository.list_tasks(
        session,
        offset=offset,
        limit=limit,
        tenant_id=tenant_id,
        status=status,
        task_type=task_type,
    )
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = str(offset + limit) if has_more else None
    return TaskPage(items=items, next_cursor=next_cursor)


def get_task(session: Session, task_id: UUID) -> Task:
    task = tasks_repository.get_task(session, task_id)
    if task is None:
        raise TaskNotFoundError(task_id)
    return task


def _cursor_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        offset = int(cursor)
    except ValueError as exc:
        raise ValueError("Pagination cursor must be a non-negative integer.") from exc
    if offset < 0:
        raise ValueError("Pagination cursor must be a non-negative integer.")
    return offset
