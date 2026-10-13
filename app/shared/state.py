from dataclasses import dataclass
from enum import StrEnum


class StateTransitionError(ValueError):
    """Raised when a requested domain state transition is not allowed."""


class TenantStatus(StrEnum):
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    UPDATING = "updating"
    DESTROYING = "destroying"
    DESTROYED = "destroyed"
    FAILED = "failed"


class TaskType(StrEnum):
    DEPLOY = "deploy"
    UPDATE = "update"
    DESTROY = "destroy"


class TaskStatus(StrEnum):
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


TERMINAL_TASK_STATUSES = frozenset({TaskStatus.DONE, TaskStatus.FAILED})


@dataclass(frozen=True)
class TaskProgressTransition:
    status: TaskStatus
    changed: bool
    terminal: bool


def start_tenant_update(status: TenantStatus) -> TenantStatus:
    if status is not TenantStatus.ACTIVE:
        raise StateTransitionError(f"Cannot update tenant from {status}.")

    return TenantStatus.UPDATING


def start_tenant_destroy(status: TenantStatus) -> TenantStatus:
    if status not in {TenantStatus.ACTIVE, TenantStatus.FAILED}:
        raise StateTransitionError(f"Cannot destroy tenant from {status}.")

    return TenantStatus.DESTROYING


def apply_task_progress(current: TaskStatus, incoming: TaskStatus) -> TaskProgressTransition:
    if incoming is TaskStatus.ACCEPTED:
        raise StateTransitionError("Worker progress cannot move a task to accepted.")

    if current in TERMINAL_TASK_STATUSES:
        return TaskProgressTransition(status=current, changed=False, terminal=True)

    if current is TaskStatus.ACCEPTED:
        if incoming in {
            TaskStatus.IN_PROGRESS,
            TaskStatus.DONE,
            TaskStatus.FAILED,
        }:
            return TaskProgressTransition(
                status=incoming,
                changed=True,
                terminal=incoming in TERMINAL_TASK_STATUSES,
            )

    if current is TaskStatus.IN_PROGRESS:
        if incoming is TaskStatus.IN_PROGRESS:
            return TaskProgressTransition(status=current, changed=False, terminal=False)

        if incoming in TERMINAL_TASK_STATUSES:
            return TaskProgressTransition(status=incoming, changed=True, terminal=True)

    raise StateTransitionError(f"Cannot move task from {current} to {incoming}.")


def apply_terminal_task_to_tenant(
    tenant_status: TenantStatus,
    task_type: TaskType,
    task_status: TaskStatus,
) -> TenantStatus:
    if task_status is TaskStatus.FAILED:
        if tenant_status not in {
            TenantStatus.PROVISIONING,
            TenantStatus.UPDATING,
            TenantStatus.DESTROYING,
        }:
            raise StateTransitionError(f"Task failure cannot apply to tenant in {tenant_status}.")

        return TenantStatus.FAILED

    if task_status is not TaskStatus.DONE:
        raise StateTransitionError("Only terminal task outcomes can update tenant state.")

    if task_type is TaskType.DEPLOY and tenant_status is TenantStatus.PROVISIONING:
        return TenantStatus.ACTIVE

    if task_type is TaskType.UPDATE and tenant_status is TenantStatus.UPDATING:
        return TenantStatus.ACTIVE

    if task_type is TaskType.DESTROY and tenant_status is TenantStatus.DESTROYING:
        return TenantStatus.DESTROYED

    raise StateTransitionError(
        f"Cannot apply {task_type} {task_status} to tenant in {tenant_status}."
    )
