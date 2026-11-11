import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    format: str
    width: int
    height: int
    size_bytes: int


class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    original_filename: str | None
    content_type: str | None
    size_bytes: int | None
    width: int | None
    height: int | None
    error: str | None
    created_at: datetime
    variants: list[VariantOut]