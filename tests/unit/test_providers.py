import pytest
from app.providers.email_provider import EmailProvider
from app.providers.sms_provider import SmsProvider
from app.providers.webhook_provider import WebhookProvider
from app.schemas.enums import NotificationStatus


def test_mock_email_provider_success():
    provider = EmailProvider()
    result = provider.send(
        recipient="test@example.com",
        subject="Welcome",
        content="Welcome to our platform!",
    )
    assert result.status == NotificationStatus.DELIVERED
    assert result.provider_message_id is not None
    assert result.status_code == 200


def test_mock_email_provider_simulated_bounce():
    provider = EmailProvider()
    result = provider.send(
        recipient="bounce@example.com",
        subject="Welcome",
        content="Hello",
    )
    assert result.status == NotificationStatus.FAILED
    assert result.retryable is False  # Hard bounce should not be retried


def test_mock_sms_provider_success():
    provider = SmsProvider()
    result = provider.send(
        recipient="+15551234567",
        subject=None,
        content="Your OTP code is 123456",
    )
    assert result.status == NotificationStatus.DELIVERED
    assert result.status_code == 200


def test_mock_webhook_provider_success():
    provider = WebhookProvider()
    result = provider.send(
        recipient="mock://webhook.receiver/event",
        subject=None,
        content='{"status": "paid"}',
    )
    assert result.status == NotificationStatus.DELIVERED
    assert result.status_code == 200
