import aio_pika
import aioboto3
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings

app = FastAPI(title="Mini Cloudinary")
engine = create_async_engine(settings.database_url)


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