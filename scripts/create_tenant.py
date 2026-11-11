"""Create a tenant, a default preset, and an API key (shown once).

Usage:
    uv run python -m scripts.create_tenant "Demo Shop" --plan free
"""
import argparse
import asyncio
import secrets

from app.auth import hash_key
from app.db import SessionLocal, engine
from app.models import ApiKey, Preset, Tenant

DEFAULT_PRESET = {
    "variants": [
        {"name": "thumb", "width": 200, "format": "webp"},
        {"name": "card", "width": 600, "format": "webp"},
        {"name": "full", "width": 1600, "format": "webp"},
    ]
}


async def main(name: str, plan: str) -> None:
    prefix = secrets.token_hex(4)
    raw_key = f"mc_{prefix}_{secrets.token_urlsafe(32)}"

    async with SessionLocal() as session:
        tenant = Tenant(name=name, plan=plan)
        session.add(tenant)
        await session.flush()
        session.add(
            ApiKey(tenant_id=tenant.id, key_prefix=prefix, key_hash=hash_key(raw_key))
        )
        session.add(Preset(tenant_id=tenant.id, name="default", config=DEFAULT_PRESET))
        await session.commit()
        tenant_id = tenant.id
    await engine.dispose()

    print(f"Tenant:  {name} ({plan})  id={tenant_id}")
    print(f"API key: {raw_key}")
    print("Save this key now. It is not stored and cannot be shown again.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--plan", choices=["free", "pro"], default="free")
    args = parser.parse_args()
    asyncio.run(main(args.name, args.plan))