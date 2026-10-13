from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from aio_pika.abc import AbstractIncomingMessage

from app.control_plane.application.progress import apply_worker_progress, parse_progress_payload
from app.shared.broker import connect_robust, decode_message_body, ensure_exchange_and_queue
from app.shared.db import SessionLocal

logger = logging.getLogger(__name__)

EXCHANGE_NAME = "tenant-provisioning"
QUEUE_NAME = "task.progress"
ROUTING_KEY = "task.progress"


async def handle_progress_message(
    session_factory: Callable[[], Any],
    raw_message: bytes | str | None,
) -> bool:
    if raw_message is None:
        return False

    try:
        payload = decode_message_body(raw_message)
    except (TypeError, ValueError):
        logger.warning("Discarding malformed worker progress payload.")
        return False

    try:
        idempotency_key, task_id, status, occurred_at = parse_progress_payload(payload)
    except ValueError:
        logger.warning("Discarding worker progress payload with missing or invalid fields.")
        return False

    with session_factory() as session:
        return bool(
            apply_worker_progress(
                session,
                idempotency_key=idempotency_key,
                task_id=task_id,
                status=status,
                occurred_at=occurred_at,
            )
        )


async def process_message(
    message: AbstractIncomingMessage,
    *,
    session_factory: Callable[[], Any] = SessionLocal,
) -> None:
    try:
        await handle_progress_message(session_factory, message.body)
    except Exception:
        logger.exception("Unexpected error while processing worker progress message.")
    if message.channel.is_closed:
        return
    await message.ack()


async def run_progress_consumer(
    *,
    session_factory: Callable[[], Any] = SessionLocal,
    rabbitmq_url: str | None = None,
    exchange_name: str = EXCHANGE_NAME,
    queue_name: str = QUEUE_NAME,
    routing_key: str = ROUTING_KEY,
    backoff_seconds: float = 1.0,
    max_backoff_seconds: float = 30.0,
) -> None:
    connection = None
    delay = backoff_seconds
    while True:
        try:
            connection = await connect_robust(rabbitmq_url or "amqp://guest:guest@localhost:5672/")
            channel = await connection.channel()
            await ensure_exchange_and_queue(channel, exchange_name, queue_name, routing_key)

            async def on_message(message: AbstractIncomingMessage) -> None:
                await process_message(message, session_factory=session_factory)

            await channel.set_qos(prefetch_count=1)
            queue = await channel.declare_queue(queue_name, durable=True)
            await queue.consume(on_message, no_ack=False)
            await asyncio.Event().wait()
        except Exception:
            logger.exception(
                "Worker progress consumer failed; retrying after %.1f seconds.",
                delay,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2.0, max_backoff_seconds)
            if connection is not None:
                try:
                    await connection.close()
                except Exception:  # pragma: no cover - defensive close
                    logger.debug("Unable to close RabbitMQ connection after retry delay.")
            continue


__all__ = [
    "EXCHANGE_NAME",
    "QUEUE_NAME",
    "ROUTING_KEY",
    "handle_progress_message",
    "process_message",
    "run_progress_consumer",
]
