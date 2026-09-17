import hashlib
import hmac
import json
import time
import uuid
from typing import Any, Dict, Optional
import httpx
from app.core.config import settings
from app.core.logging import logger
from app.providers.base import BaseNotificationProvider, ProviderResult
from app.schemas.enums import NotificationStatus


class WebhookProvider(BaseNotificationProvider):
    """
    Webhook Delivery Provider with HMAC-SHA256 Signature Verification,
    configurable timeouts, and HTTP status code retry classification.
    """

    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or settings.WEBHOOK_SECRET_KEY
        self.timeout = settings.WEBHOOK_DEFAULT_TIMEOUT_SECONDS

    def _generate_signature(self, payload_bytes: bytes, timestamp: str) -> str:
        """Compute HMAC-SHA256 signature: hmac(secret, timestamp + '.' + body)."""
        sign_payload = f"{timestamp}.".encode("utf-8") + payload_bytes
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            sign_payload,
            hashlib.sha256,
        ).hexdigest()
        return signature

    def _prepare_payload(
        self,
        recipient: str,
        subject: Optional[str],
        content: str,
        metadata: Optional[Dict[str, Any]],
    ) -> tuple[bytes, Dict[str, str], str]:
        now_ts = str(int(time.time()))
        notif_id = (metadata or {}).get("notification_id", str(uuid.uuid4()))

        # If content is valid JSON, load it, otherwise wrap it
        try:
            parsed_content = json.loads(content)
        except Exception:
            parsed_content = {"message": content}

        payload_dict = {
            "event": "notification.delivery",
            "notification_id": notif_id,
            "timestamp": now_ts,
            "subject": subject,
            "data": parsed_content,
            "metadata": metadata or {},
        }

        body_bytes = json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")
        signature = self._generate_signature(body_bytes, now_ts)

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "DistributedNotificationPlatform/1.0",
            "X-Notification-Id": notif_id,
            "X-Timestamp": now_ts,
            "X-Signature-SHA256": signature,
        }

        # Merge custom client headers from metadata if present
        if metadata and "headers" in metadata and isinstance(metadata["headers"], dict):
            headers.update(metadata["headers"])

        return body_bytes, headers, notif_id

    def send(
        self,
        recipient: str,
        subject: Optional[str],
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        start_time = time.perf_counter()
        body_bytes, headers, notif_id = self._prepare_payload(recipient, subject, content, metadata)

        # Allow simulated local webhook receiver URL without external requests
        if recipient.startswith("mock://") or "mock-webhook" in recipient:
            latency = (time.perf_counter() - start_time) * 1000 + 15.0
            logger.info(f"[Mock Webhook] Delivered event {notif_id} to {recipient}")
            return ProviderResult(
                status=NotificationStatus.DELIVERED,
                provider_name="mock_webhook",
                provider_message_id=notif_id,
                status_code=200,
                latency_ms=round(latency, 2),
                raw_response={"status": "received", "event_id": notif_id},
            )

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(recipient, content=body_bytes, headers=headers)
                latency = (time.perf_counter() - start_time) * 1000

                if 200 <= response.status_code < 300:
                    logger.info(f"Webhook delivered to {recipient} [Status {response.status_code}] in {latency:.1f}ms")
                    return ProviderResult(
                        status=NotificationStatus.DELIVERED,
                        provider_name="webhook",
                        provider_message_id=notif_id,
                        status_code=response.status_code,
                        latency_ms=round(latency, 2),
                        raw_response={"body": response.text[:200]},
                    )
                else:
                    # 5xx and 429 are retryable
                    is_retryable = response.status_code in [429, 500, 502, 503, 504]
                    logger.warning(f"Webhook returned {response.status_code} from {recipient}: {response.text[:200]}")
                    return ProviderResult(
                        status=NotificationStatus.FAILED,
                        provider_name="webhook",
                        status_code=response.status_code,
                        latency_ms=round(latency, 2),
                        error_message=f"HTTP {response.status_code}: {response.text[:200]}",
                        retryable=is_retryable,
                    )

        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
            latency = (time.perf_counter() - start_time) * 1000
            logger.error(f"Webhook connection error to {recipient}: {e}")
            return ProviderResult(
                status=NotificationStatus.FAILED,
                provider_name="webhook",
                status_code=504,
                latency_ms=round(latency, 2),
                error_message=f"Network/Timeout error: {str(e)}",
                retryable=True,
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            logger.error(f"Webhook delivery unexpected error: {e}")
            return ProviderResult(
                status=NotificationStatus.FAILED,
                provider_name="webhook",
                status_code=500,
                latency_ms=round(latency, 2),
                error_message=str(e),
                retryable=False,
            )

    async def send_async(
        self,
        recipient: str,
        subject: Optional[str],
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        start_time = time.perf_counter()
        body_bytes, headers, notif_id = self._prepare_payload(recipient, subject, content, metadata)

        if recipient.startswith("mock://") or "mock-webhook" in recipient:
            latency = (time.perf_counter() - start_time) * 1000 + 15.0
            return ProviderResult(
                status=NotificationStatus.DELIVERED,
                provider_name="mock_webhook",
                provider_message_id=notif_id,
                status_code=200,
                latency_ms=round(latency, 2),
                raw_response={"status": "received", "event_id": notif_id},
            )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(recipient, content=body_bytes, headers=headers)
                latency = (time.perf_counter() - start_time) * 1000

                if 200 <= response.status_code < 300:
                    return ProviderResult(
                        status=NotificationStatus.DELIVERED,
                        provider_name="webhook",
                        provider_message_id=notif_id,
                        status_code=response.status_code,
                        latency_ms=round(latency, 2),
                        raw_response={"body": response.text[:200]},
                    )
                else:
                    is_retryable = response.status_code in [429, 500, 502, 503, 504]
                    return ProviderResult(
                        status=NotificationStatus.FAILED,
                        provider_name="webhook",
                        status_code=response.status_code,
                        latency_ms=round(latency, 2),
                        error_message=f"HTTP {response.status_code}: {response.text[:200]}",
                        retryable=is_retryable,
                    )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return ProviderResult(
                status=NotificationStatus.FAILED,
                provider_name="webhook",
                status_code=500,
                latency_ms=round(latency, 2),
                error_message=str(e),
                retryable=True,
            )


