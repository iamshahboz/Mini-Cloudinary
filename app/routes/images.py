import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import storage
from app.auth import get_current_tenant
from app.config import settings
from app.db import get_session
from app.messaging import Publisher
from app.models import Image, Preset, Tenant
from app.schemas import ImageOut
from app.validation import ALLOWED_TYPES, sniff_image_type

router = APIRouter(prefix="/v1/images", tags=["images"])


def get_publisher(request: Request) -> Publisher:
    return request.app.state.publisher


async def fetch_image(
    session: AsyncSession, tenant_id: uuid.UUID, image_id: uuid.UUID
) -> Image | None:
    result = await session.execute(
        select(Image)
        .where(Image.id == image_id, Image.tenant_id == tenant_id)  # tenant isolation
        .options(selectinload(Image.variants))
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


@router.post("", response_model=ImageOut, status_code=202)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    preset: str | None = Form(None),
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
    publisher: Publisher = Depends(get_publisher),
):
    # 1. Cheap early rejection based on the declared size
    declared = request.headers.get("content-length")
    if declared and int(declared) > settings.max_upload_bytes + 64 * 1024:
        raise HTTPException(413, "File too large")

    # 2. Real size and real type
    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(0)
    if size == 0:
        raise HTTPException(400, "Empty file")
    if size > settings.max_upload_bytes:
        raise HTTPException(413, f"File exceeds {settings.max_upload_bytes} bytes")

    kind = sniff_image_type(file.file.read(16))
    file.file.seek(0)
    if kind is None:
        raise HTTPException(415, "Unsupported file type (JPEG, PNG, WebP only)")
    content_type, ext = ALLOWED_TYPES[kind]

    # 3. Optional preset (must belong to this tenant)
    preset_id = None
    if preset:
        found = await session.scalar(
            select(Preset).where(Preset.tenant_id == tenant.id, Preset.name == preset)
        )
        if found is None:
            raise HTTPException(404, f"Preset '{preset}' not found")
        preset_id = found.id

    # 4. Store the original, then record it
    image_id = uuid.uuid4()
    key = f"{tenant.id}/originals/{image_id}.{ext}"
    await storage.upload_original(file.file, key, content_type)

    image = Image(
        id=image_id,
        tenant_id=tenant.id,
        preset_id=preset_id,
        status="pending",
        original_key=key,
        original_filename=file.filename,
        content_type=content_type,
        size_bytes=size,
    )
    session.add(image)
    try:
        await session.commit()
    except Exception:
        await storage.delete_object(key)  # don't leave orphaned files behind
        raise

    # 5. Queue the first stage. Known gap: if this fails after the commit above,
    # we can only mark the image failed. The transactional outbox (later) closes it.
    try:
        await publisher.publish_stage(
            image_id=image_id, tenant_id=tenant.id, stage="validate", tier=tenant.plan
        )
    except Exception:
        image.status = "failed"
        image.error = "could not enqueue processing job"
        await session.commit()
        raise HTTPException(503, "Processing queue unavailable, please retry")

    return await fetch_image(session, tenant.id, image_id)


@router.get("/{image_id}", response_model=ImageOut)
async def get_image(
    image_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
):
    image = await fetch_image(session, tenant.id, image_id)
    if image is None:
        raise HTTPException(404, "Image not found")
    return image