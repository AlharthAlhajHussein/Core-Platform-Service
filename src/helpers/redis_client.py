import redis.asyncio as redis
from uuid import UUID
from helpers.config import settings

# Redis client instance
_redis_client: redis.Redis | None = None

async def get_redis_client() -> redis.Redis:
    """
    Returns an async Redis client instance. Initializes it if not already done.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            decode_responses=True # Decodes responses to strings automatically
        )
    return _redis_client

async def add_to_blocklist(user_id: UUID) -> None:
    """Adds a user's ID to the JWT blocklist in Redis."""
    client = await get_redis_client()
    # Store user_id in a set for quick lookup.
    # This blocklists all tokens for a user, forcing re-login.
    await client.sadd("jwt_blocklist", str(user_id))

async def is_blocklisted(user_id: UUID) -> bool:
    """Checks if a user's ID is in the JWT blocklist."""
    client = await get_redis_client()
    return await client.sismember("jwt_blocklist", str(user_id))
