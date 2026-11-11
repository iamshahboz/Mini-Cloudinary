from typing import BinaryIO

import aioboto3

from app.config import settings

_session = aioboto3.Session()


def _client():
    return _session.client(
        "s3",
        region_name=settings.s3_region,
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )


async def upload_original(fileobj: BinaryIO, key: str, content_type: str) -> None:
    async with _client() as s3:
        await s3.upload_fileobj(
            fileobj,
            settings.s3_bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )


async def delete_object(key: str) -> None:
    async with _client() as s3:
        await s3.delete_object(Bucket=settings.s3_bucket, Key=key)