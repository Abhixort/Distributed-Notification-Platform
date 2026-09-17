import time
from typing import Dict, Tuple
from app.core.config import settings
from app.core.logging import logger
from app.core.metrics import RATE_LIMIT_DROPPED
from app.core.redis import TOKEN_BUCKET_LUA_SCRIPT, get_async_redis


class InMemoryTokenBucket:
    """In-memory fallback token bucket for standalone runs / testing when Redis is offline."""
    def __init__(self):
        self._buckets: Dict[str, Dict[str, float]] = {}

    def consume(self, key: str, capacity: int, refill_rate: float, cost: int = 1) -> Tuple[bool, float, int]:
        now = time.time()
        bucket = self._buckets.get(key)
        if not bucket:
            tokens = capacity - cost
            self._buckets[key] = {"tokens": tokens, "last_updated": now}
            return True, 0.0, int(tokens)

        last_updated = bucket["last_updated"]
        current_tokens = bucket["tokens"]
        elapsed = max(0.0, now - last_updated)
        current_tokens = min(float(capacity), current_tokens + (elapsed * refill_rate))

        if current_tokens >= cost:
            current_tokens -= cost
            self._buckets[key] = {"tokens": current_tokens, "last_updated": now}
            return True, 0.0, int(current_tokens)
        else:
            missing = cost - current_tokens
            retry_after = missing / refill_rate
            self._buckets[key] = {"tokens": current_tokens, "last_updated": now}
            return False, retry_after, int(current_tokens)


_in_memory_limiter = InMemoryTokenBucket()


class TokenBucketRateLimiter:
    """
    High-Throughput Token Bucket Rate Limiter.
    Utilizes atomic Redis Lua script to support 10,000+ operations/min with zero race conditions.
    Falls back gracefully to in-memory bucket if Redis is not accessible.
    """

    def __init__(
        self,
        capacity: int = settings.DEFAULT_RATE_LIMIT_CAPACITY,
        refill_rate: float = settings.DEFAULT_RATE_LIMIT_REFILL_RATE,
    ):
        self.default_capacity = capacity
        self.default_refill_rate = refill_rate

    async def check_rate_limit(
        self,
        client_id: str = "global",
        channel: str = "all",
        capacity: int = None,
        refill_rate: float = None,
        cost: int = 1,
    ) -> Tuple[bool, float, int]:
        """
        Check and consume tokens from token bucket.
        Returns: (allowed: bool, retry_after_seconds: float, remaining_tokens: int)
        """
        if not settings.RATE_LIMIT_ENABLED:
            return True, 0.0, 9999

        cap = capacity or self.default_capacity
        rate = refill_rate or self.default_refill_rate
        now = time.time()

        from app.core.redis import is_redis_available
        if not is_redis_available():
            allowed, retry_after, remaining = _in_memory_limiter.consume(
                key=f"{client_id}:{channel}",
                capacity=cap,
                refill_rate=rate,
                cost=cost,
            )
            if not allowed:
                RATE_LIMIT_DROPPED.labels(channel=channel, client_id=client_id).inc()
            return allowed, retry_after, remaining

        key_prefix = f"rate_limit:{client_id}:{channel}"
        tokens_key = f"{key_prefix}:tokens"
        timestamp_key = f"{key_prefix}:ts"

        try:
            redis_client = await get_async_redis()
            # Execute atomic Lua script in Redis
            result = await redis_client.eval(
                TOKEN_BUCKET_LUA_SCRIPT,
                2,
                tokens_key,
                timestamp_key,
                cap,
                rate,
                cost,
                now,
            )

            status = int(result[0])
            val = float(result[1])

            if status == 1:
                return True, 0.0, int(val)
            else:
                RATE_LIMIT_DROPPED.labels(channel=channel, client_id=client_id).inc()
                logger.warning(
                    f"Rate limit exceeded for client '{client_id}' on channel '{channel}' (retry after {val:.2f}s)"
                )
                return False, val, 0

        except Exception as e:
            logger.debug(f"Redis rate limiter fallback to in-memory: {e}")
            allowed, retry_after, remaining = _in_memory_limiter.consume(
                key=f"{client_id}:{channel}",
                capacity=cap,
                refill_rate=rate,
                cost=cost,
            )
            if not allowed:
                RATE_LIMIT_DROPPED.labels(channel=channel, client_id=client_id).inc()
            return allowed, retry_after, remaining


rate_limiter = TokenBucketRateLimiter()
