from __future__ import annotations

import json
from typing import Any

import pytest

from scripts.publish_progress import publish_progress


@pytest.mark.asyncio
async def test_repeated_manual_progress_uses_the_same_idempotency_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeExchange:
        def __init__(self, channel: FakeChannel) -> None:
            self.channel = channel

        async def publish(self, message: Any, routing_key: str) -> None:
            self.channel.messages.append(json.loads(message.body))

    class FakeChannel:
        def __init__(self) -> None:
            self.messages: list[dict[str, Any]] = []

        async def declare_exchange(self, *args: Any, **kwargs: Any) -> FakeExchange:
            return FakeExchange(self)

    class FakeConnection:
        def __init__(self) -> None:
            self.channel_instance = FakeChannel()

        async def channel(self) -> FakeChannel:
            return self.channel_instance

        async def close(self) -> None:
            return None

    connection = FakeConnection()

    async def connect_robust(_url: str) -> FakeConnection:
        return connection

    monkeypatch.setattr("scripts.publish_progress.aio_pika.connect_robust", connect_robust)

    await publish_progress(
        rabbitmq_url="amqp://localhost/",
        task_id="task-id",
        status="in_progress",
        worker_id="demo-worker",
        exchange_name="tenant-provisioning",
        routing_key="task.progress",
        idempotency_key="duplicate-demo",
        repeat=2,
    )

    assert [message["id"] for message in connection.channel_instance.messages] == [
        "duplicate-demo",
        "duplicate-demo",
    ]
