import pytest
from app.models.notification import Notification
from app.schemas.enums import ChannelType, NotificationStatus
from app.services.idempotency import idempotency_service


@pytest.mark.asyncio
async def test_idempotency_new_key_returns_true(db_session):
    key = "unique-test-key-12345"
    is_new, existing = await idempotency_service.check_or_lock(key, db_session)
    assert is_new is True
    assert existing is None
    await idempotency_service.release_lock(key)


@pytest.mark.asyncio
async def test_idempotency_existing_notification_returns_cached(db_session):
    key = "existing-key-abc"
    # Seed notification in DB
    notification = Notification(
        channel=ChannelType.EMAIL.value,
        recipient="user@test.com",
        idempotency_key=key,
        status=NotificationStatus.DELIVERED.value,
    )
    db_session.add(notification)
    await db_session.commit()

    is_new, existing = await idempotency_service.check_or_lock(key, db_session)
    assert is_new is False
    assert existing is not None
    assert existing.idempotency_key == key
