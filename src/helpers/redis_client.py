import redis.asyncio as redis
from uuid import UUID
from helpers import settings

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

async def delete_agent_config_cache(agent_id: UUID = None, platform: str = None, identifier: str = None) -> None:
    """Deletes the cached configuration for a specific agent."""
    client = await get_redis_client()
    # This key format must match what the Gateway and Orchestrator services use for caching.
    if not agent_id:
        await client.delete(f"agent_config:{str(agent_id)}")
    if not platform and not identifier:
        await client.delete(f"agent_config:{platform}:{identifier}")
    
async def block_token(token: str, ttl: int) -> None:
    """Adds a specific token to the blocklist with a Time-To-Live (TTL)."""
    if ttl > 0:
        client = await get_redis_client()
        await client.setex(f"token_blocklist:{token}", ttl, "true")

async def is_token_blocked(token: str) -> bool:
    """Checks if a specific token is in the blocklist."""
    client = await get_redis_client()
    return await client.exists(f"token_blocklist:{token}") > 0
