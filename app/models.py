import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


def created_at_col() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (CheckConstraint("plan IN ('free','pro')", name="ck_tenants_plan"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200))
    plan: Mapped[str] = mapped_column(String(20), server_default="free")
    monthly_upload_quota: Mapped[int] = mapped_column(Integer, server_default="1000")
    webhook_url: Mapped[str | None] = mapped_column(Text)
    webhook_secret: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = created_at_col()

    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="tenant")
    presets: Mapped[list["Preset"]] = relationship(back_populates="tenant")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    key_prefix: Mapped[str] = mapped_column(String(12), unique=True)
    key_hash: Mapped[str] = mapped_column(String(64))  # sha256 hex
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = created_at_col()
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant: Mapped[Tenant] = relationship(back_populates="api_keys")


class Preset(Base):
    """Per-tenant definition of which variants to produce, e.g.
    {"variants": [{"name": "thumb", "width": 200, "format": "webp"}]}"""

    __tablename__ = "presets"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_presets_tenant_name"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    config: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at_col()

    tenant: Mapped[Tenant] = relationship(back_populates="presets")


class Image(Base):
    __tablename__ = "images"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','processing','completed','failed','rejected')",
            name="ck_images_status",
        ),
        Index("ix_images_tenant_created", "tenant_id", "created_at"),
        Index("ix_images_phash", "phash"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    preset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("presets.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    original_key: Mapped[str] = mapped_column(Text)
    original_filename: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    phash: Mapped[int | None] = mapped_column(BigInteger)  # 64-bit perceptual hash
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("images.id", ondelete="SET NULL")
    )
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    variants: Mapped[list["ImageVariant"]] = relationship(
        back_populates="image", cascade="all, delete-orphan"
    )
    stage_runs: Mapped[list["StageRun"]] = relationship(
        back_populates="image", cascade="all, delete-orphan"
    )


class ImageVariant(Base):
    __tablename__ = "image_variants"
    __table_args__ = (UniqueConstraint("image_id", "name", name="uq_variants_image_name"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    image_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("images.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    storage_key: Mapped[str] = mapped_column(Text)
    format: Mapped[str] = mapped_column(String(10))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = created_at_col()

    image: Mapped[Image] = relationship(back_populates="variants")


class StageRun(Base):
    """One row per (image, stage). The unique constraint is our idempotency key."""

    __tablename__ = "stage_runs"
    __table_args__ = (
        UniqueConstraint("image_id", "stage", name="uq_stage_runs_image_stage"),
        CheckConstraint(
            "status IN ('running','succeeded','failed')", name="ck_stage_runs_status"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    image_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("images.id", ondelete="CASCADE"), index=True
    )
    stage: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), server_default="running")
    attempts: Mapped[int] = mapped_column(Integer, server_default="1")
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = created_at_col()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    image: Mapped[Image] = relationship(back_populates="stage_runs")