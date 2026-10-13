from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime

import aio_pika


def build_payload(
    *,
    task_id: str,
    status: str,
    worker_id: str,
    occurred_at: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, str]:
    timestamp = occurred_at or datetime.now(UTC).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )
    return {
        "id": idempotency_key or f"manual-{task_id}-{status}-{worker_id}",
        "task_id": task_id,
        "status": status,
        "occurred_at": timestamp,
        "worker_id": worker_id,
    }


async def publish_progress(
    *,
    rabbitmq_url: str,
    task_id: str,
    status: str,
    worker_id: str,
    exchange_name: str,
    routing_key: str,
    occurred_at: str | None = None,
    idempotency_key: str | None = None,
    repeat: int = 1,
) -> None:
    """Publish manual progress events for negative scenario demos.

    Example:
        python scripts/publish_progress.py \
            --task-id <uuid> --status in_progress --worker-id demo-worker \
            --idempotency-key stale-in-progress --rabbitmq-url amqp://guest:guest@localhost:5672/
    """
    connection = await aio_pika.connect_robust(rabbitmq_url)
    try:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
        )
        for index in range(repeat):
            payload = build_payload(
                task_id=task_id,
                status=status,
                worker_id=worker_id,
                occurred_at=occurred_at,
                idempotency_key=idempotency_key if repeat == 1 else f"{idempotency_key}-{index}",
            )
            message = aio_pika.Message(
                body=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )
            await exchange.publish(message, routing_key=routing_key)
            print(f"published {index + 1}/{repeat}: {payload}")
    finally:
        await connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Publish manual worker progress messages to RabbitMQ for demos and negative scenarios."
        )
    )
    parser.add_argument(
        "--rabbitmq-url", default="amqp://guest:guest@localhost:5672/", help="RabbitMQ URL."
    )
    parser.add_argument("--task-id", required=True, help="UUID of the task to update.")
    parser.add_argument(
        "--status",
        choices=["in_progress", "done", "failed"],
        required=True,
        help="Worker status to emit.",
    )
    parser.add_argument(
        "--worker-id",
        default="manual-worker",
        help="Worker identity used in the published message.",
    )
    parser.add_argument("--exchange", default="tenant-provisioning", help="RabbitMQ exchange name.")
    parser.add_argument("--routing-key", default="task.progress", help="RabbitMQ routing key.")
    parser.add_argument(
        "--idempotency-key", default=None, help="Stable idempotency key used by the consumer."
    )
    parser.add_argument(
        "--occurred-at", default=None, help="ISO-8601 timestamp for the progress event."
    )
    parser.add_argument("--repeat", type=int, default=1, help="Repeat the same message N times.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    if args.repeat < 1:
        raise ValueError("--repeat must be at least 1.")
    await publish_progress(
        rabbitmq_url=args.rabbitmq_url,
        task_id=args.task_id,
        status=args.status,
        worker_id=args.worker_id,
        exchange_name=args.exchange,
        routing_key=args.routing_key,
        occurred_at=args.occurred_at,
        idempotency_key=args.idempotency_key,
        repeat=args.repeat,
    )


if __name__ == "__main__":
    asyncio.run(main())
