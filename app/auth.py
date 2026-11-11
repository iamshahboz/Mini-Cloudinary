import hashlib
import hmac

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import ApiKey, Tenant

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def parse_prefix(raw: str) -> str | None:
    """Keys look like mc_<prefix>_<secret>; the secret may contain '_' or '-'."""
    parts = raw.split("_", 2)
    if len(parts) != 3 or parts[0] != "mc":
        return None
    return parts[1]


async def get_current_tenant(
    raw_key: str | None = Depends(api_key_header),
    session: AsyncSession = Depends(get_session),
) -> Tenant:
    unauthorized = HTTPException(
        status_code=401,
        detail="Invalid or missing API key",
        headers={"WWW-Authenticate": "ApiKey"},
    )
    if not raw_key:
        raise unauthorized
    prefix = parse_prefix(raw_key)
    if prefix is None:
        raise unauthorized

    result = await session.execute(
        select(ApiKey, Tenant)
        .join(Tenant, Tenant.id == ApiKey.tenant_id)
        .where(ApiKey.key_prefix == prefix, ApiKey.is_active.is_(True))
    )
    row = result.first()
    if row is None:
        raise unauthorized
    api_key, tenant = row
    if not hmac.compare_digest(api_key.key_hash, hash_key(raw_key)):
        raise unauthorized
    return tenant