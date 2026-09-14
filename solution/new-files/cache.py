"""
Revenue summary cache.

BUG 1 FIX (cross-tenant cache key collision):
The previous key was f"revenue:{property_id}" — tenant_id was never part of
the key. Since seed data has prop-001 existing under both tenant-a
("Beach House Alpha") and tenant-b ("Mountain Lodge Beta"), whichever
tenant's request landed first populated the shared key, and the other
tenant was served that cached data for the TTL window. The key now
includes tenant_id, so each tenant gets its own cache entry even when
property_ids collide across tenants.
"""
import json
from typing import Dict, Any, Optional

try:
    import redis.asyncio as redis
except ImportError:  # redis client optional in some environments
    redis = None

CACHE_TTL_SECONDS = 300  # 5 minutes

_redis_client: Optional["redis.Redis"] = None


def _get_redis_client():
    global _redis_client
    if redis is None:
        return None
    if _redis_client is None:
        _redis_client = redis.from_url("redis://localhost:6379/0", decode_responses=True)
    return _redis_client


def _cache_key(property_id: str, tenant_id: str) -> str:
    # Tenant-scoped key — this is the actual fix for Bug 1.
    return f"revenue:{tenant_id}:{property_id}"


async def get_revenue_summary(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Returns the revenue summary for (property_id, tenant_id), preferring a
    tenant-scoped cache entry and falling back to computing it fresh.
    """
    client = _get_redis_client()
    key = _cache_key(property_id, tenant_id)

    if client is not None:
        try:
            cached = await client.get(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            print(f"Cache read error for {key}: {e}")

    # Local import avoids a circular import between cache <-> reservations.
    from app.services.reservations import calculate_total_revenue
    revenue_data = await calculate_total_revenue(property_id, tenant_id)

    if client is not None:
        try:
            await client.set(key, json.dumps(revenue_data), ex=CACHE_TTL_SECONDS)
        except Exception as e:
            print(f"Cache write error for {key}: {e}")

    return revenue_data