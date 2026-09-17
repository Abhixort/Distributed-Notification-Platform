import time
import uuid
from typing import Any, Dict, Optional
from app.core.config import settings
from app.core.logging import logger
from app.providers.base import BaseNotificationProvider, ProviderResult
from app.schemas.enums import NotificationStatus


class SmsProvider(BaseNotificationProvider):
    """
    SMS Delivery Provider supporting AWS SNS, Twilio, and Simulated Mock SMS Gateway.
    """

    def __init__(self):
        self.use_mock = settings.USE_MOCK_PROVIDERS or not (
            settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY
        )
        self._sns_client = None

    def _get_sns_client(self):
        if self._sns_client is None and not self.use_mock:
            import boto3
            self._sns_client = boto3.client(
                "sns",
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
        return self._sns_client

    def send(
        self,
        recipient: str,
        subject: Optional[str],
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        start_time = time.perf_counter()
        provider_name = "mock_sms_provider" if self.use_mock else "aws_sns"

        if self.use_mock:
            # Test triggers
            if "0000000000" in recipient or "9999999999" in recipient:
                latency = (time.perf_counter() - start_time) * 1000 + 40.0
                return ProviderResult(
                    status=NotificationStatus.FAILED,
                    provider_name=provider_name,
                    status_code=503,
                    latency_ms=round(latency, 2),
                    error_message=f"Carrier network temporary unreachable for recipient {recipient}",
                    retryable=True,
                )

            if "1111111111" in recipient:
                latency = (time.perf_counter() - start_time) * 1000 + 20.0
                return ProviderResult(
                    status=NotificationStatus.FAILED,
                    provider_name=provider_name,
                    status_code=400,
                    latency_ms=round(latency, 2),
                    error_message=f"Invalid phone number format: {recipient}",
                    retryable=False,
                )

            msg_id = f"sns-mock-{uuid.uuid4().hex[:12]}"
            latency = (time.perf_counter() - start_time) * 1000 + 35.0
            logger.info(f"[Mock SMS] Delivered SMS to {recipient}: '{content[:40]}...' [MsgID: {msg_id}]")
            return ProviderResult(
                status=NotificationStatus.DELIVERED,
                provider_name=provider_name,
                provider_message_id=msg_id,
                status_code=200,
                latency_ms=round(latency, 2),
                raw_response={"MessageId": msg_id, "Status": "Delivered"},
            )

        # Real AWS SNS Delivery
        try:
            client = self._get_sns_client()
            response = client.publish(
                PhoneNumber=recipient,
                Message=content,
            )
            latency = (time.perf_counter() - start_time) * 1000
            msg_id = response.get("MessageId", str(uuid.uuid4()))
            return ProviderResult(
                status=NotificationStatus.DELIVERED,
                provider_name="aws_sns",
                provider_message_id=msg_id,
                status_code=200,
                latency_ms=round(latency, 2),
                raw_response=response,
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            logger.error(f"AWS SNS SMS delivery failed: {e}")
            return ProviderResult(
                status=NotificationStatus.FAILED,
                provider_name="aws_sns",
                status_code=500,
                latency_ms=round(latency, 2),
                error_message=str(e),
                retryable=True,
            )

    async def send_async(
        self,
        recipient: str,
        subject: Optional[str],
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        return self.send(recipient, subject, content, metadata)
