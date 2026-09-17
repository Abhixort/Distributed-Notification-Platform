import json
from typing import Any, Dict, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.exceptions import IdempotencyConflictException
from app.core.logging import logger
from app.core.metrics import IDEMPOTENCY_HITS
from app.core.redis import get_async_redis
from app.models.notification import Notification


class InMemoryIdempotencyStore:
    """In-memory fallback store for idempotency keys when Redis is offline."""
    def __init__(self):
        self._locks: Dict[str, float] = {}
        self._results: Dict[str, Dict[str, Any]] = {}

    def acquire(self, key: str) -> bool:
        import time
        now = time.time()
        if key in self._locks and self._locks[key] > now:
            return False
        self._locks[key] = now + settings.IDEMPOTENCY_LOCK_TIMEOUT_SECONDS
        return True

    def release(self, key: str):
        self._locks.pop(key, None)

    def cache_result(self, key: str, data: Dict[str, Any]):
        self._results[key] = data

    def get_result(self, key: str) -> Optional[Dict[str, Any]]:
        return self._results.get(key)


_in_memory_idempotency = InMemoryIdempotencyStore()


class IdempotencyService:
    """
    Dual-Tier Idempotency Management:
    1. Distributed Lock (Redis SET NX EX) to prevent simultaneous duplicate requests.
    2. Atomic DB check / Redis result cache for deterministic, idempotent replay.
    """

    @staticmethod
    async def check_or_lock(
        idempotency_key: str,
        db_session: AsyncSession,
    ) -> Tuple[bool, Optional[Notification]]:
        """
        Attempts to acquire lock for key or returns existing notification if already processed.
        Returns:
            (is_new_request: bool, existing_notification: Optional[Notification])
        Raises:
            IdempotencyConflictException if identical request is currently processing in-flight.
        """
        if not idempotency_key:
            return True, None

        lock_key = f"idempotency:lock:{idempotency_key}"

        # 1. Check Database for already processed notification
        query = select(Notification).where(Notification.idempotency_key == idempotency_key)
        result = await db_session.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            IDEMPOTENCY_HITS.labels(channel=existing.channel).inc()
            logger.info(f"Idempotency hit: returning existing notification '{existing.id}' for key '{idempotency_key}'")
            return False, existing

        # 2. Acquire Redis distributed lock
        from app.core.redis import is_redis_available
        if not is_redis_available():
            if not _in_memory_idempotency.acquire(idempotency_key):
                raise IdempotencyConflictException(idempotency_key)
            return True, None

        try:
            redis_client = await get_async_redis()
            acquired = await redis_client.set(
                lock_key,
                "in_progress",
                nx=True,
                ex=settings.IDEMPOTENCY_LOCK_TIMEOUT_SECONDS,
            )
            if not acquired:
                logger.warning(f"Concurrent request detected for idempotency key '{idempotency_key}'")
                raise IdempotencyConflictException(idempotency_key)
        except IdempotencyConflictException:
            raise
        except Exception as e:
            logger.debug(f"Redis lock fallback to in-memory: {e}")
            if not _in_memory_idempotency.acquire(idempotency_key):
                raise IdempotencyConflictException(idempotency_key)

        return True, None

    @staticmethod
    async def release_lock(idempotency_key: str):
        """Release the in-flight lock after notification is safely queued/persisted."""
        if not idempotency_key:
            return

        lock_key = f"idempotency:lock:{idempotency_key}"
        try:
            redis_client = await get_async_redis()
            await redis_client.delete(lock_key)
        except Exception:
            _in_memory_idempotency.release(idempotency_key)


idempotency_service = IdempotencyService()
