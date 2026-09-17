import pytest
from app.services.rate_limiter import InMemoryTokenBucket, TokenBucketRateLimiter


def test_in_memory_token_bucket_allows_under_limit():
    bucket = InMemoryTokenBucket()
    allowed, retry_after, remaining = bucket.consume(
        key="client1:email",
        capacity=10,
        refill_rate=5.0,
        cost=1,
    )
    assert allowed is True
    assert retry_after == 0.0
    assert remaining == 9


def test_in_memory_token_bucket_rejects_burst_exceeding_capacity():
    bucket = InMemoryTokenBucket()
    key = "burst_client:sms"

    # Consume all 3 tokens
    for _ in range(3):
        allowed, _, _ = bucket.consume(key=key, capacity=3, refill_rate=1.0, cost=1)
        assert allowed is True

    # 4th request must be rejected
    allowed, retry_after, remaining = bucket.consume(key=key, capacity=3, refill_rate=1.0, cost=1)
    assert allowed is False
    assert retry_after > 0.0
    assert remaining == 0


@pytest.mark.asyncio
async def test_token_bucket_rate_limiter_service():
    limiter = TokenBucketRateLimiter(capacity=20, refill_rate=10.0)
    allowed, retry_after, remaining = await limiter.check_rate_limit(
        client_id="unit_test_client",
        channel="webhook",
        capacity=20,
        refill_rate=10.0,
        cost=1,
    )
    assert allowed is True
    assert retry_after == 0.0
