from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
from collections.abc import Iterable
from typing import Any
from uuid import UUID

from aio_pika.abc import AbstractIncomingMessage

from app.shared.broker import (
    connect_robust,
    decode_message_body,
    ensure_exchange_and_queue,
    publish_payload,
)
from app.shared.time import format_utc_millis, utc_now

logger = logging.getLogger(__name__)

EXCHANGE_NAME = "tenant-provisioning"
QUEUE_NAME = "task.created"
ROUTING_KEY = "task.created"
PROGRESS_EXCHANGE_NAME = EXCHANGE_NAME
PROGRESS_ROUTING_KEY = "task.progress"


def parse_task_created_payload(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        raise ValueError("Task-created payload must be a JSON object.")

    if payload.get("event_type") != "task.created":
        raise ValueError("Task-created payload must contain event_type=task.created.")

    task_payload = payload.get("task")
    if not isinstance(task_payload, dict):
        raise ValueError("Task-created payload is missing a task object.")

    raw_task_id = task_payload.get("id") or payload.get("id")
    if not isinstance(raw_task_id, str) or not raw_task_id.strip():
        raise ValueError("Task-created payload is missing task id.")

    try:
        task_id = str(UUID(raw_task_id))
    except ValueError as exc:
        raise ValueError("Task-created payload contains an invalid task UUID.") from exc

    status = task_payload.get("status")
    if not isinstance(status, str) or not status:
        raise ValueError("Task-created payload is missing a task status.")

    if status not in {"accepted", "in_progress", "done", "failed"}:
        raise ValueError(f"Unsupported task status in task-created payload: {status}")

    return task_id


def stable_progress_id(task_id: str, status: str, worker_id: str) -> str:
    digest = hashlib.sha256(f"{task_id}|{status}|{worker_id}".encode()).hexdigest()
    return digest


def build_progress_payload(
    task_id: str,
    status: str,
    *,
    worker_id: str,
    occurred_at: str | None = None,
) -> dict[str, str]:
    if status not in {"in_progress", "done", "failed"}:
        raise ValueError(f"Unsupported worker progress status: {status}")

    timestamp = occurred_at or format_utc_millis(utc_now())
    return {
        "id": stable_progress_id(task_id, status, worker_id),
        "task_id": str(task_id),
        "status": status,
        "occurred_at": timestamp,
        "worker_id": worker_id,
    }


def should_fail_task(task_id: str, *, fail_rate: float, worker_id: str = "worker-1") -> bool:
    if not 0.0 <= fail_rate <= 1.0:
        raise ValueError("fail_rate must be between 0.0 and 1.0.")
    if fail_rate in {0.0, 1.0}:
        return fail_rate == 1.0

    seed = hashlib.sha256(f"{task_id}|{worker_id}|fail".encode()).hexdigest()
    normalized = int(seed, 16) / float(16 ** len(seed))
    return normalized < fail_rate


def resolve_delay_ms(
    task_id: str,
    *,
    min_delay_ms: int,
    max_delay_ms: int,
    worker_id: str = "worker-1",
) -> int:
    if min_delay_ms < 0 or max_delay_ms < 0:
        raise ValueError("Delay values must be non-negative.")
    if max_delay_ms < min_delay_ms:
        raise ValueError("max_delay_ms must be greater than or equal to min_delay_ms.")

    span = max(0, max_delay_ms - min_delay_ms)
    seed = hashlib.sha256(f"{task_id}|{worker_id}|delay".encode()).hexdigest()
    offset = int(seed, 16) % (span + 1)
    return min_delay_ms + offset


def build_progress_updates(
    task_id: str,
    *,
    fail_rate: float,
    min_delay_ms: int,
    max_delay_ms: int,
    worker_id: str,
) -> list[dict[str, str]]:
    if not task_id:
        raise ValueError("task_id must not be empty.")

    terminal_status = (
        "failed" if should_fail_task(task_id, fail_rate=fail_rate, worker_id=worker_id) else "done"
    )
    updates: list[dict[str, str]] = []
    _ = resolve_delay_ms(
        task_id,
        min_delay_ms=min_delay_ms,
        max_delay_ms=max_delay_ms,
        worker_id=worker_id,
    )
    updates.append(build_progress_payload(task_id, "in_progress", worker_id=worker_id))
    updates.append(build_progress_payload(task_id, terminal_status, worker_id=worker_id))
    return updates


async def handle_task_created_message(
    channel: Any,
    raw_message: bytes | str | None,
    *,
    fail_rate: float = 0.0,
    min_delay_ms: int = 0,
    max_delay_ms: int = 0,
    worker_id: str = "worker-1",
) -> bool:
    if raw_message is None:
        return False

    try:
        payload = decode_message_body(raw_message)
    except (TypeError, ValueError):
        logger.warning("Discarding malformed task-created payload.")
        return False

    try:
        task_id = parse_task_created_payload(payload)
    except ValueError:
        logger.warning("Discarding task-created payload with missing or invalid fields.")
        return False

    updates = build_progress_updates(
        task_id,
        fail_rate=fail_rate,
        min_delay_ms=min_delay_ms,
        max_delay_ms=max_delay_ms,
        worker_id=worker_id,
    )

    for index, update in enumerate(updates):
        if index > 0:
            delay_ms = resolve_delay_ms(
                task_id,
                min_delay_ms=min_delay_ms,
                max_delay_ms=max_delay_ms,
                worker_id=worker_id,
            )
            if delay_ms > 0:
                await asyncio.sleep(delay_ms / 1000)
        await publish_payload(channel, PROGRESS_EXCHANGE_NAME, PROGRESS_ROUTING_KEY, update)

    return True


async def process_task_message(
    message: AbstractIncomingMessage,
    *,
    channel: Any,
    fail_rate: float = 0.0,
    min_delay_ms: int = 0,
    max_delay_ms: int = 0,
    worker_id: str = "worker-1",
) -> None:
    try:
        await handle_task_created_message(
            channel,
            message.body,
            fail_rate=fail_rate,
            min_delay_ms=min_delay_ms,
            max_delay_ms=max_delay_ms,
            worker_id=worker_id,
        )
    except Exception:
        logger.exception("Unexpected error while processing task-created message.")
    if message.channel.is_closed:
        return
    await message.ack()


async def run_worker_simulator(
    *,
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/",
    exchange_name: str = EXCHANGE_NAME,
    queue_name: str = QUEUE_NAME,
    routing_key: str = ROUTING_KEY,
    fail_rate: float = 0.0,
    min_delay_ms: int = 0,
    max_delay_ms: int = 0,
    worker_id: str = "worker-1",
    backoff_seconds: float = 1.0,
    max_backoff_seconds: float = 30.0,
) -> None:
    connection = None
    delay = backoff_seconds
    while True:
        try:
            connection = await connect_robust(rabbitmq_url)
            channel = await connection.channel()
            await ensure_exchange_and_queue(channel, exchange_name, queue_name, routing_key)

            def make_on_message(current_channel: Any):
                async def on_message(message: AbstractIncomingMessage) -> None:
                    await process_task_message(
                        message,
                        channel=current_channel,
                        fail_rate=fail_rate,
                        min_delay_ms=min_delay_ms,
                        max_delay_ms=max_delay_ms,
                        worker_id=worker_id,
                    )

                return on_message

            await channel.set_qos(prefetch_count=1)
            queue = await channel.declare_queue(queue_name, durable=True)
            await queue.consume(make_on_message(channel), no_ack=False)
            await asyncio.Event().wait()
        except Exception:
            logger.exception(
                "Worker simulator failed; retrying after %.1f seconds.",
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simulate tenant provisioning tasks.")
    parser.add_argument("--fail-rate", type=float, default=0.0, help="Probability the task fails.")
    parser.add_argument(
        "--min-delay-ms",
        type=int,
        default=0,
        help="Minimum simulated delay between worker progress updates.",
    )
    parser.add_argument(
        "--max-delay-ms",
        type=int,
        default=0,
        help="Maximum simulated delay between worker progress updates.",
    )
    parser.add_argument("--worker-id", default="worker-1", help="Stable worker identifier.")
    parser.add_argument(
        "--rabbitmq-url",
        default="amqp://guest:guest@localhost:5672/",
        help="RabbitMQ connection string.",
    )
    return parser


async def _main(argv: Iterable[str] | None = None) -> None:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    if not 0.0 <= args.fail_rate <= 1.0:
        raise ValueError("--fail-rate must be between 0.0 and 1.0.")
    if args.min_delay_ms < 0 or args.max_delay_ms < 0:
        raise ValueError("--min-delay-ms and --max-delay-ms must be non-negative.")
    if args.max_delay_ms < args.min_delay_ms:
        raise ValueError("--max-delay-ms must be greater than or equal to --min-delay-ms.")
    await run_worker_simulator(
        rabbitmq_url=args.rabbitmq_url,
        fail_rate=args.fail_rate,
        min_delay_ms=args.min_delay_ms,
        max_delay_ms=args.max_delay_ms,
        worker_id=args.worker_id,
    )


if __name__ == "__main__":
    asyncio.run(_main())
