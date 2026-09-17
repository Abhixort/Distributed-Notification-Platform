from typing import Dict, Optional
from app.core.exceptions import NotificationPlatformException
from app.core.logging import logger
from app.providers.base import BaseNotificationProvider
from app.providers.email_provider import EmailProvider
from app.providers.sms_provider import SmsProvider
from app.providers.webhook_provider import WebhookProvider
from app.schemas.enums import ChannelType


class ProviderFactory:
    """
    Factory creating and managing delivery provider instances for each channel.
    Supports channel routing and circuit-breaker / fallback strategy.
    """

    def __init__(self):
        self._providers: Dict[str, BaseNotificationProvider] = {
            ChannelType.EMAIL.value: EmailProvider(),
            ChannelType.SMS.value: SmsProvider(),
            ChannelType.WEBHOOK.value: WebhookProvider(),
        }

    def get_provider(self, channel: str) -> BaseNotificationProvider:
        channel_key = channel.lower()
        if channel_key not in self._providers:
            raise NotificationPlatformException(f"Unsupported notification channel: '{channel}'")
        return self._providers[channel_key]

    def register_provider(self, channel: str, provider: BaseNotificationProvider):
        """Allow runtime registration or mocking of custom providers."""
        self._providers[channel.lower()] = provider


provider_factory = ProviderFactory()
