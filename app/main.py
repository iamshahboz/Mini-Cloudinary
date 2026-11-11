from contextlib import asynccontextmanager

import aio_pika
import aioboto3
from fastapi import FastAPI
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.messaging import Publisher
from app.routes import images


@asynccontextmanager
async def lifespan(app: FastAPI):
    publisher = Publisher()
    await publisher.connect()  # also declares exchange + queues
    app.state.publisher = publisher
    yield
    await publisher.close()
    await engine.dispose()


app = FastAPI(title="Mini Cloudinary", lifespan=lifespan)
app.include_router(images.router)


async def check_postgres() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def check_rabbitmq() -> bool:
    try:
        conn = await aio_pika.connect_robust(settings.rabbitmq_url)
        await conn.close()
        return True
    except Exception:
        return False


async def check_storage() -> bool:
    try:
        session = aioboto3.Session()
        async with session.client(
            "s3",
            region_name=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
        ) as s3:
            await s3.head_bucket(Bucket=settings.s3_bucket)
        return True
    except Exception:
        return False


@app.get("/health")
async def health():
    checks = {
        "postgres": await check_postgres(),
        "rabbitmq": await check_rabbitmq(),
        "storage": await check_storage(),
    }
    return {"status": "ok" if all(checks.values()) else "degraded", **checks}