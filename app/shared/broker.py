from __future__ import annotations

import json
from typing import Any

import aio_pika
from aio_pika import Message
from aio_pika.abc import AbstractChannel


async def connect_robust(rabbitmq_url: str) -> aio_pika.abc.AbstractRobustConnection:
    return await aio_pika.connect_robust(rabbitmq_url)


async def ensure_exchange_and_queue(
    channel: AbstractChannel,
    exchange_name: str,
    queue_name: str,
    routing_key: str,
) -> tuple[aio_pika.abc.AbstractExchange, aio_pika.abc.AbstractQueue]:
    exchange = await channel.declare_exchange(
        exchange_name,
        aio_pika.ExchangeType.TOPIC,
        durable=True,
    )
    queue = await channel.declare_queue(queue_name, durable=True)
    await queue.bind(exchange, routing_key=routing_key)
    return exchange, queue


async def publish_payload(
    channel: AbstractChannel,
    exchange_name: str,
    routing_key: str,
    payload: dict[str, Any],
) -> None:
    exchange = await channel.declare_exchange(
        exchange_name,
        aio_pika.ExchangeType.TOPIC,
        durable=True,
    )
    message = Message(
        body=json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"),
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )
    await exchange.publish(message, routing_key=routing_key)
