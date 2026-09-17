from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from app.schemas.enums import NotificationStatus


@dataclass
class ProviderResult:
    status: NotificationStatus
    provider_name: str
    provider_message_id: Optional[str] = None
    status_code: Optional[int] = None
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    retryable: bool = False
    raw_response: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BaseNotificationProvider(ABC):
    """Abstract interface for all multi-channel downstream notification delivery gateways."""

    @abstractmethod
    def send(
        self,
        recipient: str,
        subject: Optional[str],
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        """Synchronous send method for Celery worker tasks."""
        pass

    @abstractmethod
    async def send_async(
        self,
        recipient: str,
        subject: Optional[str],
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        """Asynchronous send method for async worker contexts / direct invocations."""
        pass
