import json

import aio_pika

from app.config import settings

EXCHANGE_NAME = "images"
STAGES = ["validate"]  # later steps add: strip, resize, compress, ...
TIERS = ["free", "pro"]


def routing_key(stage: str, tier: str) -> str:
    return f"{stage}.{tier}"


def queue_name(stage: str, tier: str) -> str:
    return f"{stage}.{tier}"


async def declare_topology(channel) -> aio_pika.abc.AbstractExchange:
    """Idempotent: safe to run on every startup (API and workers)."""
    exchange = await channel.declare_exchange(
        EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
    )
    for stage in STAGES:
        for tier in TIERS:
            queue = await channel.declare_queue(queue_name(stage, tier), durable=True)
            await queue.bind(exchange, routing_key=routing_key(stage, tier))
    return exchange


class Publisher:
    def __init__(self) -> None:
        self._connection = None
        self._channel = None
        self._exchange = None

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        # confirms: publish() waits for the broker's ack;
        # on_return_raises: an unroutable message raises instead of vanishing
        self._channel = await self._connection.channel(
            publisher_confirms=True, on_return_raises=True
        )
        self._exchange = await declare_topology(self._channel)

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()

    async def publish_stage(
        self, *, image_id, tenant_id, stage: str, tier: str, attempt: int = 1
    ) -> None:
        body = json.dumps(
            {
                "image_id": str(image_id),
                "tenant_id": str(tenant_id),
                "stage": stage,
                "attempt": attempt,
            }
        ).encode()
        message = aio_pika.Message(
            body=body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            message_id=f"{image_id}:{stage}",
        )
        await self._exchange.publish(
            message, routing_key=routing_key(stage, tier), timeout=5
        )