from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.control_plane.application.progress import apply_worker_progress
from app.control_plane.repositories import tasks, tenants
from app.outbox_publisher.publisher import OutboxPublisher
from app.shared.db import Base
from app.shared.models import OutboxEvent
from app.shared.state import TaskStatus, TaskType, TenantStatus


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_duplicate_worker_progress_delivery_changes_state_only_once(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        tenant = tenants.add_tenant(
            session,
            slug="progress-duplicate",
            name="Duplicate Progress",
            status=TenantStatus.PROVISIONING,
        )
        task = tasks.add_task(session, tenant_id=tenant.id, task_type=TaskType.DEPLOY)
        task.status = TaskStatus.ACCEPTED
        session.flush()

        first = apply_worker_progress(
            session,
            idempotency_key="duplicate-progress",
            task_id=task.id,
            status=TaskStatus.IN_PROGRESS.value,
            occurred_at="2024-01-01T00:00:00Z",
        )
        second = apply_worker_progress(
            session,
            idempotency_key="duplicate-progress",
            task_id=task.id,
            status=TaskStatus.IN_PROGRESS.value,
            occurred_at="2024-01-01T00:00:10Z",
        )

    assert first is True
    assert second is False
    assert task.status is TaskStatus.IN_PROGRESS
    assert tenant.status is TenantStatus.PROVISIONING


def test_out_of_order_worker_progress_delivery_does_not_regress_terminal_task(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        tenant = tenants.add_tenant(
            session,
            slug="terminal-stale",
            name="Terminal Stale",
            status=TenantStatus.ACTIVE,
        )
        task = tasks.add_task(session, tenant_id=tenant.id, task_type=TaskType.UPDATE)
        task.status = TaskStatus.DONE
        session.flush()

        handled = apply_worker_progress(
            session,
            idempotency_key="stale-in-progress",
            task_id=task.id,
            status=TaskStatus.IN_PROGRESS.value,
            occurred_at="2024-01-01T00:00:00Z",
        )

    assert handled is False
    assert task.status is TaskStatus.DONE
    assert tenant.status is TenantStatus.ACTIVE


@pytest.mark.asyncio
async def test_outbox_publisher_delivers_the_stored_payload(
    session_factory: sessionmaker[Session],
) -> None:
    class FakeExchange:
        def __init__(self, channel: FakeChannel) -> None:
            self.channel = channel

        async def publish(self, message: Any, routing_key: str) -> None:
            self.channel.messages.append((routing_key, message.body))

    class FakeChannel:
        def __init__(self) -> None:
            self.messages: list[tuple[str, bytes]] = []

        async def declare_exchange(self, *args: Any, **kwargs: Any) -> FakeExchange:
            return FakeExchange(self)

    row = OutboxEvent(
        id=uuid4(),
        event_type="task.created",
        exchange="tenant-provisioning",
        routing_key="task.created",
        payload={
            "id": "stored-task-id",
            "event_type": "task.created",
            "task": {"status": "accepted"},
        },
    )

    with session_factory() as session:
        session.add(row)
        session.commit()

    channel = FakeChannel()
    publisher = OutboxPublisher(session_factory=session_factory, batch_size=10, poll_interval=0)
    await publisher.publish_pending_batch(channel)

    assert channel.messages == [
        (
            "task.created",
            b'{"event_type":"task.created","id":"stored-task-id","task":{"status":"accepted"}}',
        )
    ]

    with session_factory() as session:
        stored = session.get(OutboxEvent, row.id)
        assert stored is not None
        assert stored.published_at is not None
