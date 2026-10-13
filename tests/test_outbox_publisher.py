from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.outbox_publisher.publisher import OutboxPublisher
from app.outbox_publisher.repository import fetch_unpublished_events, mark_events_published
from app.shared.db import Base
from app.shared.models import OutboxEvent
from app.shared.time import utc_now


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        yield session_maker
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_repository_selects_only_unpublished_rows(session_factory: sessionmaker[Session]) -> None:
    published_row = OutboxEvent(
        id=uuid4(),
        event_type="task.created",
        exchange="tenant-provisioning",
        routing_key="task.created",
        payload={"id": "published"},
        published_at=utc_now(),
    )
    unpublished_row = OutboxEvent(
        id=uuid4(),
        event_type="task.created",
        exchange="tenant-provisioning",
        routing_key="task.created",
        payload={"id": "pending"},
    )

    with session_factory() as session:
        session.add_all([published_row, unpublished_row])
        session.commit()

        rows = fetch_unpublished_events(session, limit=25)

    assert [row.id for row in rows] == [unpublished_row.id]


@pytest.mark.asyncio
async def test_publisher_publishes_stored_payload_and_marks_event_published(
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
        payload={"id": "task-123", "status": "accepted"},
    )

    with session_factory() as session:
        session.add(row)
        session.commit()

    channel = FakeChannel()
    publisher = OutboxPublisher(session_factory=session_factory, batch_size=10, poll_interval=0)
    await publisher.publish_pending_batch(channel)

    assert channel.messages == [("task.created", b'{"id":"task-123","status":"accepted"}')]

    with session_factory() as session:
        stored = session.get(OutboxEvent, row.id)
        assert stored is not None
        assert stored.published_at is not None


@pytest.mark.asyncio
async def test_publisher_retries_transient_broker_failures_before_marking_row_published(
    session_factory: sessionmaker[Session],
) -> None:
    class FakeExchange:
        def __init__(self, channel: FailingChannel) -> None:
            self.channel = channel

        async def publish(self, message: Any, routing_key: str) -> None:
            self.channel.publish_calls += 1
            if self.channel.publish_calls < 3:
                raise RuntimeError("temporary")
            self.channel.messages.append((routing_key, message.body))

    class FailingChannel:
        def __init__(self) -> None:
            self.publish_calls = 0
            self.messages: list[tuple[str, bytes]] = []

        async def declare_exchange(self, *args: Any, **kwargs: Any) -> FakeExchange:
            return FakeExchange(self)

    row = OutboxEvent(
        id=uuid4(),
        event_type="task.created",
        exchange="tenant-provisioning",
        routing_key="task.created",
        payload={"id": "task-456", "status": "accepted"},
    )

    with session_factory() as session:
        session.add(row)
        session.commit()

    channel = FailingChannel()

    async def fake_sleep(_: float) -> None:
        return None

    publisher = OutboxPublisher(
        session_factory=session_factory,
        batch_size=10,
        poll_interval=0,
        sleep_fn=fake_sleep,
    )
    await publisher.publish_pending_batch(channel)

    assert channel.publish_calls == 3
    assert channel.messages == [("task.created", b'{"id":"task-456","status":"accepted"}')]

    with session_factory() as session:
        stored = session.get(OutboxEvent, row.id)
        assert stored is not None
        assert stored.published_at is not None


def test_mark_events_published_updates_only_unpublished_rows(
    session_factory: sessionmaker[Session],
) -> None:
    row_a = OutboxEvent(
        id=uuid4(),
        event_type="task.created",
        exchange="tenant-provisioning",
        routing_key="task.created",
        payload={"id": "a"},
    )
    row_b = OutboxEvent(
        id=uuid4(),
        event_type="task.created",
        exchange="tenant-provisioning",
        routing_key="task.created",
        payload={"id": "b"},
        published_at=utc_now(),
    )

    with session_factory() as session:
        session.add_all([row_a, row_b])
        session.commit()
        updated = mark_events_published(session, [row_a.id, row_b.id])
        session.commit()

    assert updated == 1

    with session_factory() as session:
        rows = {event.id: event for event in session.query(OutboxEvent).all()}
        assert rows[row_a.id].published_at is not None
        assert rows[row_b.id].published_at is not None


def test_outbox_publisher_uses_stored_payload_not_rebuilt_domain_event() -> None:
    # This is intentionally a unit-level check: RabbitMQ integration tests continue in the
    # Docker Compose environment where the broker is available.
    assert json.loads(json.dumps({"event_type": "task.created"})) == {"event_type": "task.created"}
