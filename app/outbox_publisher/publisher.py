from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from app.outbox_publisher.repository import fetch_unpublished_events, mark_events_published
from app.shared.broker import connect_robust, ensure_exchange_and_queue, publish_payload
from app.shared.config import get_settings
from app.shared.db import SessionLocal
from app.shared.models import OutboxEvent

logger = logging.getLogger(__name__)

DEFAULT_EXCHANGE = "tenant-provisioning"
DEFAULT_QUEUE = "task.created"
DEFAULT_ROUTING_KEY = "task.created"


class OutboxPublisher:
    def __init__(
        self,
        *,
        session_factory: Any | None = None,
        rabbitmq_url: str | None = None,
        batch_size: int | None = None,
        poll_interval: float | None = None,
        sleep_fn: Callable[[float], Any] | None = None,
    ) -> None:
        settings = get_settings()
        self.session_factory = session_factory or SessionLocal
        self.rabbitmq_url = rabbitmq_url or settings.rabbitmq_url
        self.batch_size = batch_size if batch_size is not None else settings.outbox_batch_size
        self.poll_interval = (
            poll_interval if poll_interval is not None else settings.outbox_poll_interval_seconds
        )
        self.sleep_fn = sleep_fn or asyncio.sleep

    async def publish_row(self, channel: Any, row: OutboxEvent, *, max_retries: int = 3) -> None:
        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                await publish_payload(channel, row.exchange, row.routing_key, row.payload)
                break
            except Exception as exc:  # pragma: no cover - exercised through the higher-level loop
                last_error = exc
                if attempt == max_retries:
                    raise
                backoff_seconds = min(2**attempt, 30)
                logger.warning(
                    "Broker publish failed for outbox row %s (attempt %s/%s); retrying in %ss",
                    row.id,
                    attempt,
                    max_retries,
                    backoff_seconds,
                )
                await self.sleep_fn(backoff_seconds)

        with self.session_factory() as session:
            mark_events_published(session, [row.id])
            session.commit()

        if last_error is not None:
            logger.info("Published outbox row %s after transient broker retries.", row.id)

    async def publish_pending_batch(self, channel: Any) -> int:
        with self.session_factory() as session:
            rows = fetch_unpublished_events(session, limit=self.batch_size)

        published = 0
        for row in rows:
            try:
                await self.publish_row(channel, row)
            except Exception:
                logger.exception(
                    "Failed to publish outbox row %s; it will be retried on the next poll.",
                    row.id,
                )
                continue
            published += 1

        return published

    async def run(self) -> None:
        connection = await connect_robust(self.rabbitmq_url)
        channel = await connection.channel()
        await ensure_exchange_and_queue(
            channel,
            DEFAULT_EXCHANGE,
            DEFAULT_QUEUE,
            DEFAULT_ROUTING_KEY,
        )

        try:
            while True:
                try:
                    await self.publish_pending_batch(channel)
                except Exception:
                    logger.exception("Outbox publisher batch failed; retrying after backoff.")
                await self.sleep_fn(self.poll_interval)
        finally:
            await connection.close()


async def publish_pending_events(
    *,
    channel: Any,
    session_factory: Any | None = None,
    batch_size: int | None = None,
    rabbitmq_url: str | None = None,
) -> int:
    publisher = OutboxPublisher(
        session_factory=session_factory,
        rabbitmq_url=rabbitmq_url,
        batch_size=batch_size,
        poll_interval=0,
    )
    return await publisher.publish_pending_batch(channel)


publish_pending_rows = publish_pending_events
