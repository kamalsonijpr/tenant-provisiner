import pytest

from app.shared.state import (
    StateTransitionError,
    TaskStatus,
    TaskType,
    TenantStatus,
    apply_task_progress,
    apply_terminal_task_to_tenant,
    start_tenant_destroy,
    start_tenant_update,
)


def test_start_tenant_update_only_allows_active() -> None:
    assert start_tenant_update(TenantStatus.ACTIVE) is TenantStatus.UPDATING

    with pytest.raises(StateTransitionError):
        start_tenant_update(TenantStatus.PROVISIONING)


@pytest.mark.parametrize(
    "status",
    [TenantStatus.ACTIVE, TenantStatus.FAILED],
)
def test_start_tenant_destroy_allows_active_or_failed(status: TenantStatus) -> None:
    assert start_tenant_destroy(status) is TenantStatus.DESTROYING


@pytest.mark.parametrize(
    "status",
    [
        TenantStatus.PROVISIONING,
        TenantStatus.UPDATING,
        TenantStatus.DESTROYING,
        TenantStatus.DESTROYED,
    ],
)
def test_start_tenant_destroy_rejects_other_statuses(status: TenantStatus) -> None:
    with pytest.raises(StateTransitionError):
        start_tenant_destroy(status)


@pytest.mark.parametrize(
    ("current", "incoming", "expected", "terminal"),
    [
        (TaskStatus.ACCEPTED, TaskStatus.IN_PROGRESS, TaskStatus.IN_PROGRESS, False),
        (TaskStatus.IN_PROGRESS, TaskStatus.DONE, TaskStatus.DONE, True),
        (TaskStatus.IN_PROGRESS, TaskStatus.FAILED, TaskStatus.FAILED, True),
        (TaskStatus.ACCEPTED, TaskStatus.DONE, TaskStatus.DONE, True),
        (TaskStatus.ACCEPTED, TaskStatus.FAILED, TaskStatus.FAILED, True),
    ],
)
def test_apply_task_progress_allows_valid_forward_transitions(
    current: TaskStatus,
    incoming: TaskStatus,
    expected: TaskStatus,
    terminal: bool,
) -> None:
    transition = apply_task_progress(current, incoming)

    assert transition.status is expected
    assert transition.changed is True
    assert transition.terminal is terminal


def test_apply_task_progress_ignores_duplicate_in_progress() -> None:
    transition = apply_task_progress(TaskStatus.IN_PROGRESS, TaskStatus.IN_PROGRESS)

    assert transition.status is TaskStatus.IN_PROGRESS
    assert transition.changed is False
    assert transition.terminal is False


@pytest.mark.parametrize("terminal_status", [TaskStatus.DONE, TaskStatus.FAILED])
def test_apply_task_progress_ignores_updates_for_terminal_tasks(
    terminal_status: TaskStatus,
) -> None:
    transition = apply_task_progress(terminal_status, TaskStatus.IN_PROGRESS)

    assert transition.status is terminal_status
    assert transition.changed is False
    assert transition.terminal is True


@pytest.mark.parametrize(
    ("current", "incoming"),
    [
        (TaskStatus.ACCEPTED, TaskStatus.ACCEPTED),
        (TaskStatus.IN_PROGRESS, TaskStatus.ACCEPTED),
    ],
)
def test_apply_task_progress_rejects_invalid_worker_transitions(
    current: TaskStatus,
    incoming: TaskStatus,
) -> None:
    with pytest.raises(StateTransitionError):
        apply_task_progress(current, incoming)


@pytest.mark.parametrize(
    ("tenant_status", "task_type", "expected"),
    [
        (TenantStatus.PROVISIONING, TaskType.DEPLOY, TenantStatus.ACTIVE),
        (TenantStatus.UPDATING, TaskType.UPDATE, TenantStatus.ACTIVE),
        (TenantStatus.DESTROYING, TaskType.DESTROY, TenantStatus.DESTROYED),
    ],
)
def test_apply_done_task_to_tenant_allows_matching_state_machine_paths(
    tenant_status: TenantStatus,
    task_type: TaskType,
    expected: TenantStatus,
) -> None:
    assert apply_terminal_task_to_tenant(tenant_status, task_type, TaskStatus.DONE) is expected


@pytest.mark.parametrize(
    "tenant_status",
    [TenantStatus.PROVISIONING, TenantStatus.UPDATING, TenantStatus.DESTROYING],
)
def test_apply_failed_task_to_tenant_marks_failed(tenant_status: TenantStatus) -> None:
    assert (
        apply_terminal_task_to_tenant(
            tenant_status,
            TaskType.DEPLOY,
            TaskStatus.FAILED,
        )
        is TenantStatus.FAILED
    )


def test_apply_terminal_task_to_tenant_rejects_mismatched_task_type() -> None:
    with pytest.raises(StateTransitionError):
        apply_terminal_task_to_tenant(
            TenantStatus.PROVISIONING,
            TaskType.UPDATE,
            TaskStatus.DONE,
        )
