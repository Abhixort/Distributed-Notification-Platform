import time
from typing import Optional, Tuple
import redis
import redis.asyncio as aioredis
from app.core.config import settings
from app.core.logging import logger

# ---------------------------------------------------------------------------
# Redis Connection Pools & Availability Tracking
# ---------------------------------------------------------------------------
async_redis_pool: Optional[aioredis.ConnectionPool] = None
async_redis_client: Optional[aioredis.Redis] = None
sync_redis_client: Optional[redis.Redis] = None
_redis_is_available: Optional[bool] = None


def set_redis_availability(available: bool):
    global _redis_is_available
    _redis_is_available = available


def is_redis_available() -> bool:
    global _redis_is_available
    if _redis_is_available is None:
        return True
    return _redis_is_available


def get_sync_redis() -> redis.Redis:
    """Get or initialize synchronous Redis client."""
    global sync_redis_client
    if sync_redis_client is None:
        sync_redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=0.5,
            socket_connect_timeout=0.2,
        )
    return sync_redis_client


async def get_async_redis() -> aioredis.Redis:
    """Get or initialize asynchronous Redis client."""
    global async_redis_pool, async_redis_client
    if async_redis_client is None:
        async_redis_pool = aioredis.ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
            socket_timeout=0.5,
            socket_connect_timeout=0.2,
        )
        async_redis_client = aioredis.Redis(connection_pool=async_redis_pool)
    return async_redis_client


async def close_redis():
    """Close Redis connection pools on shutdown."""
    global async_redis_client, async_redis_pool
    if async_redis_client:
        await async_redis_client.aclose()
    if async_redis_pool:
        await async_redis_pool.disconnect()
    logger.info("Redis connection pool closed.")


# ---------------------------------------------------------------------------
# Atomic Lua Script: Token-Bucket Rate Limiter (High Throughput 10k+/min)
# ---------------------------------------------------------------------------
# Keys:
#   1: tokens_key (stores float token count)
#   2: timestamp_key (stores float last_updated timestamp)
# Args:
#   1: capacity (max tokens)
#   2: refill_rate (tokens per second)
#   3: requested_tokens (e.g. 1)
#   4: current_timestamp (now in seconds)
# Returns:
#   [1, remaining_tokens] if allowed
#   [0, retry_after_seconds] if rejected
TOKEN_BUCKET_LUA_SCRIPT = """
local tokens_key = KEYS[1]
local timestamp_key = KEYS[2]

local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local requested = tonumber(ARGV[3])
local now = tonumber(ARGV[4])
local ttl = math.ceil(capacity / refill_rate) * 2

local current_tokens = tonumber(redis.call('get', tokens_key))
local last_updated = tonumber(redis.call('get', timestamp_key))

if not current_tokens then
    current_tokens = capacity
    last_updated = now
else
    local elapsed = math.max(0, now - last_updated)
    current_tokens = math.min(capacity, current_tokens + (elapsed * refill_rate))
    last_updated = now
end

if current_tokens >= requested then
    current_tokens = current_tokens - requested
    redis.call('setex', tokens_key, ttl, current_tokens)
    redis.call('setex', timestamp_key, ttl, last_updated)
    return {1, current_tokens}
else
    local missing = requested - current_tokens
    local retry_after = missing / refill_rate
    redis.call('setex', tokens_key, ttl, current_tokens)
    redis.call('setex', timestamp_key, ttl, last_updated)
    return {0, retry_after}
end
"""


# ---------------------------------------------------------------------------
# Atomic Lua Script: Distributed Idempotency Lock
# ---------------------------------------------------------------------------
# Tries to acquire an idempotency lock for key, or check if already cached
IDEMPOTENCY_LOCK_LUA_SCRIPT = """
local lock_key = KEYS[1]
local result_key = KEYS[2]
local lock_val = ARGV[1]
local lock_ttl = tonumber(ARGV[2])

local cached_res = redis.call('get', result_key)
if cached_res then
    return {'CACHED', cached_res}
end

local acquired = redis.call('set', lock_key, lock_val, 'NX', 'EX', lock_ttl)
if acquired then
    return {'ACQUIRED', ''}
else
    return {'LOCKED', ''}
end
"""
