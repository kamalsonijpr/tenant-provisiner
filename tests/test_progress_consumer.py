from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.control_plane.application.progress import apply_worker_progress
from app.control_plane.repositories import tasks, tenants
from app.shared.models import Base
from app.shared.state import TaskStatus, TaskType, TenantStatus


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as session:
        yield session


def _iso_utc(offset_seconds: int = 0) -> str:
    timestamp = datetime.now(UTC) + timedelta(seconds=offset_seconds)
    return timestamp.isoformat().replace("+00:00", "Z")


def test_progress_consumer_ignores_duplicate_updates(session: Session) -> None:
    tenant = tenants.add_tenant(
        session,
        slug="dup-tenant",
        name="Duplicate Tenant",
        status=TenantStatus.PROVISIONING,
    )
    task = tasks.add_task(session, tenant_id=tenant.id, task_type=TaskType.DEPLOY)
    task.status = TaskStatus.ACCEPTED
    session.flush()

    first = apply_worker_progress(
        session,
        idempotency_key="dup-progress-1",
        task_id=task.id,
        status=TaskStatus.IN_PROGRESS.value,
        occurred_at=_iso_utc(),
    )
    second = apply_worker_progress(
        session,
        idempotency_key="dup-progress-1",
        task_id=task.id,
        status=TaskStatus.IN_PROGRESS.value,
        occurred_at=_iso_utc(5),
    )

    assert first is True
    assert second is False
    assert task.status is TaskStatus.IN_PROGRESS
    assert tenant.status is TenantStatus.PROVISIONING


def test_progress_consumer_ignores_stale_updates(session: Session) -> None:
    tenant = tenants.add_tenant(
        session,
        slug="stale-tenant",
        name="Stale Tenant",
        status=TenantStatus.PROVISIONING,
    )
    task = tasks.add_task(session, tenant_id=tenant.id, task_type=TaskType.DEPLOY)
    task.status = TaskStatus.DONE
    session.flush()

    handled = apply_worker_progress(
        session,
        idempotency_key="stale-progress-1",
        task_id=task.id,
        status=TaskStatus.IN_PROGRESS.value,
        occurred_at=_iso_utc(),
    )

    assert handled is False
    assert task.status is TaskStatus.DONE
    assert tenant.status is TenantStatus.PROVISIONING


def test_progress_consumer_applies_terminal_task_result_to_tenant(session: Session) -> None:
    tenant = tenants.add_tenant(
        session,
        slug="terminal-tenant",
        name="Terminal Tenant",
        status=TenantStatus.PROVISIONING,
    )
    task = tasks.add_task(session, tenant_id=tenant.id, task_type=TaskType.DEPLOY)
    task.status = TaskStatus.ACCEPTED
    session.flush()

    handled = apply_worker_progress(
        session,
        idempotency_key="terminal-progress-1",
        task_id=task.id,
        status=TaskStatus.DONE.value,
        occurred_at=_iso_utc(),
    )

    assert handled is True
    assert task.status is TaskStatus.DONE
    assert tenant.status is TenantStatus.ACTIVE
    assert tenant.version == 2


def test_progress_consumer_applies_failed_terminal_task_result(session: Session) -> None:
    tenant = tenants.add_tenant(
        session,
        slug="failed-tenant",
        name="Failed Tenant",
        status=TenantStatus.UPDATING,
    )
    task = tasks.add_task(session, tenant_id=tenant.id, task_type=TaskType.UPDATE)
    task.status = TaskStatus.IN_PROGRESS
    session.flush()

    handled = apply_worker_progress(
        session,
        idempotency_key="failed-progress-1",
        task_id=task.id,
        status=TaskStatus.FAILED.value,
        occurred_at=_iso_utc(),
    )

    assert handled is True
    assert task.status is TaskStatus.FAILED
    assert tenant.status is TenantStatus.FAILED
    assert tenant.version == 2
