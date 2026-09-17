from typing import Any, Optional


class NotificationPlatformException(Exception):
    """Base exception for Distributed Notification Platform."""
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.details = details


class RateLimitExceededException(NotificationPlatformException):
    """Raised when request rate exceeds the allowed token bucket threshold."""
    def __init__(self, retry_after: float = 1.0, limit: int = 100, remaining: int = 0):
        super().__init__(
            message=f"Rate limit exceeded. Try again in {retry_after:.2f} seconds.",
            details={"retry_after": retry_after, "limit": limit, "remaining": remaining}
        )
        self.retry_after = retry_after
        self.limit = limit
        self.remaining = remaining


class IdempotencyConflictException(NotificationPlatformException):
    """Raised when an operation with the same idempotency key is already in progress."""
    def __init__(self, idempotency_key: str):
        super().__init__(
            message=f"A request with idempotency key '{idempotency_key}' is currently being processed.",
            details={"idempotency_key": idempotency_key}
        )
        self.idempotency_key = idempotency_key


class ProviderDeliveryError(NotificationPlatformException):
    """Raised when a downstream delivery gateway (SES, SNS, Webhook) fails."""
    def __init__(self, channel: str, provider: str, error_message: str, status_code: Optional[int] = None, retryable: bool = True):
        super().__init__(
            message=f"Delivery failed via {provider} ({channel}): {error_message}",
            details={"channel": channel, "provider": provider, "status_code": status_code, "retryable": retryable}
        )
        self.channel = channel
        self.provider = provider
        self.status_code = status_code
        self.retryable = retryable


class TemplateRenderError(NotificationPlatformException):
    """Raised when dynamic template variable interpolation fails."""
    pass


class ResourceNotFoundException(NotificationPlatformException):
    """Raised when requested entity is not found."""
    pass
