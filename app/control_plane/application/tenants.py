from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.control_plane.api.errors import (
    TenantAlreadyExistsError,
    TenantNotFoundError,
    TenantUpdateNotAllowedError,
    TenantVersionConflictError,
)
from app.control_plane.repositories import outbox, tasks, tenants
from app.shared.models import Task, Tenant
from app.shared.state import (
    StateTransitionError,
    TaskType,
    TenantStatus,
    start_tenant_destroy,
    start_tenant_update,
)
from app.shared.time import format_utc_millis


@dataclass(frozen=True)
class TenantPage:
    items: list[Tenant]
    next_cursor: str | None


def create_tenant(session: Session, *, slug: str, name: str) -> Tenant:
    try:
        with session.begin():
            tenant = tenants.add_tenant(
                session,
                slug=slug,
                name=name,
                status=TenantStatus.PROVISIONING,
            )
            task = tasks.add_task(
                session,
                tenant_id=tenant.id,
                task_type=TaskType.DEPLOY,
            )
            timestamp = format_utc_millis(task.created_at)
            outbox.add_task_created_event(
                session,
                task_id=task.id,
                occurred_at=timestamp,
                task_payload=_task_payload(task),
            )
            return tenant
    except IntegrityError as exc:
        if _is_slug_unique_violation(exc):
            raise TenantAlreadyExistsError(slug) from exc
        raise


def get_tenant(session: Session, tenant_id: UUID) -> Tenant:
    tenant = tenants.get_tenant(session, tenant_id)
    if tenant is None:
        raise TenantNotFoundError(tenant_id)
    return tenant


def list_tenants(
    session: Session,
    *,
    limit: int,
    cursor: str | None,
    status: TenantStatus | None,
) -> TenantPage:
    offset = _cursor_offset(cursor)
    rows = tenants.list_tenants(session, offset=offset, limit=limit, status=status)
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = str(offset + limit) if has_more else None
    return TenantPage(items=items, next_cursor=next_cursor)


def update_tenant(
    session: Session,
    *,
    tenant_id: UUID,
    name: str,
    version: int,
) -> Tenant:
    with session.begin():
        tenant = tenants.get_tenant(session, tenant_id)
        if tenant is None:
            raise TenantNotFoundError(tenant_id)
        if tenant.version != version:
            raise TenantVersionConflictError(version, tenant.version)
        try:
            new_status = start_tenant_update(tenant.status)
        except StateTransitionError as exc:
            raise TenantUpdateNotAllowedError(tenant.status.value, "updated") from exc

        if not tenants.update_tenant_if_version_matches(
            session,
            tenant_id=tenant_id,
            version=version,
            name=name,
            current_status=tenant.status,
            new_status=new_status,
        ):
            _raise_mutation_conflict(session, tenant_id, version, "updated")
        session.refresh(tenant)
        task = tasks.add_task(
            session,
            tenant_id=tenant.id,
            task_type=TaskType.UPDATE,
        )
        timestamp = format_utc_millis(task.created_at)
        outbox.add_task_created_event(
            session,
            task_id=task.id,
            occurred_at=timestamp,
            task_payload=_task_payload(task),
        )
        return tenant


def delete_tenant(session: Session, *, tenant_id: UUID, version: int) -> Tenant:
    with session.begin():
        tenant = tenants.get_tenant(session, tenant_id)
        if tenant is None:
            raise TenantNotFoundError(tenant_id)
        if tenant.version != version:
            raise TenantVersionConflictError(version, tenant.version)
        try:
            new_status = start_tenant_destroy(tenant.status)
        except StateTransitionError as exc:
            raise TenantUpdateNotAllowedError(tenant.status.value, "deleted") from exc

        if not tenants.transition_tenant_if_version_matches(
            session,
            tenant_id=tenant_id,
            version=version,
            current_statuses=(TenantStatus.ACTIVE, TenantStatus.FAILED),
            new_status=new_status,
        ):
            _raise_mutation_conflict(session, tenant_id, version, "deleted")
        session.refresh(tenant)
        task = tasks.add_task(
            session,
            tenant_id=tenant.id,
            task_type=TaskType.DESTROY,
        )
        timestamp = format_utc_millis(task.created_at)
        outbox.add_task_created_event(
            session,
            task_id=task.id,
            occurred_at=timestamp,
            task_payload=_task_payload(task),
        )
        return tenant


def _raise_mutation_conflict(
    session: Session,
    tenant_id: UUID,
    expected_version: int,
    operation: str,
) -> None:
    tenant = tenants.reload_tenant(session, tenant_id)
    if tenant is None:
        raise TenantNotFoundError(tenant_id)
    if tenant.version != expected_version:
        raise TenantVersionConflictError(expected_version, tenant.version)
    raise TenantUpdateNotAllowedError(tenant.status.value, operation)


def _task_payload(task: Task) -> dict[str, str]:
    return {
        "id": str(task.id),
        "type": task.type.value,
        "tenant_id": str(task.tenant_id),
        "status": task.status.value,
        "created_at": format_utc_millis(task.created_at),
        "updated_at": format_utc_millis(task.updated_at),
    }


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


def _is_slug_unique_violation(exc: IntegrityError) -> bool:
    constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    if constraint_name == "uq_tenants_slug":
        return True
    return "UNIQUE constraint failed: tenants.slug" in str(exc.orig)
