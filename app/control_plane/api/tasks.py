from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.control_plane.api.schemas import PaginatedResponse, TaskResponse
from app.control_plane.application import tasks
from app.shared.db import get_session
from app.shared.state import TaskStatus, TaskType

router = APIRouter(prefix="/tasks", tags=["tasks"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.get("", response_model=PaginatedResponse[TaskResponse], status_code=status.HTTP_200_OK)
def list_tasks_endpoint(
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(pattern=r"^\d+$")] = None,
    tenant_id: Annotated[UUID | None, Query()] = None,
    status: Annotated[TaskStatus | None, Query()] = None,
    task_type: Annotated[TaskType | None, Query(alias="type")] = None,
) -> PaginatedResponse[TaskResponse]:
    page = tasks.list_tasks(
        session,
        limit=limit,
        cursor=cursor,
        tenant_id=tenant_id,
        status=status,
        task_type=task_type,
    )
    return PaginatedResponse[TaskResponse](
        items=[TaskResponse.model_validate(task) for task in page.items],
        next_cursor=page.next_cursor,
    )


@router.get("/{task_id}", response_model=TaskResponse, status_code=status.HTTP_200_OK)
def get_task_endpoint(task_id: UUID, session: SessionDependency) -> TaskResponse:
    task = tasks.get_task(session, task_id)
    return TaskResponse.model_validate(task)
