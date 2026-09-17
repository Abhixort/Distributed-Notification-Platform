import time
import uuid
from typing import Any, Dict, Optional
from app.core.config import settings
from app.core.logging import logger
from app.providers.base import BaseNotificationProvider, ProviderResult
from app.schemas.enums import NotificationStatus


class EmailProvider(BaseNotificationProvider):
    """
    Email Delivery Provider supporting AWS SES and Simulated Mock Gateway.
    """

    def __init__(self):
        self.use_mock = settings.USE_MOCK_PROVIDERS or not (
            settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY
        )
        self.sender = settings.SES_SENDER_EMAIL
        self._ses_client = None

    def _get_ses_client(self):
        if self._ses_client is None and not self.use_mock:
            import boto3
            self._ses_client = boto3.client(
                "ses",
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
        return self._ses_client

    def send(
        self,
        recipient: str,
        subject: Optional[str],
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        start_time = time.perf_counter()
        provider_name = "mock_email_provider" if self.use_mock else "aws_ses"

        if self.use_mock:
            # High-fidelity mock email delivery simulation
            # Support test failure triggers (e.g. recipient contains 'fail@' or 'bounce@')
            if "fail@" in recipient.lower():
                latency = (time.perf_counter() - start_time) * 1000 + 45.0
                return ProviderResult(
                    status=NotificationStatus.FAILED,
                    provider_name=provider_name,
                    status_code=500,
                    latency_ms=round(latency, 2),
                    error_message=f"Simulated upstream SMTP 500 error for {recipient}",
                    retryable=True,
                )

            if "bounce@" in recipient.lower():
                latency = (time.perf_counter() - start_time) * 1000 + 30.0
                return ProviderResult(
                    status=NotificationStatus.FAILED,
                    provider_name=provider_name,
                    status_code=400,
                    latency_ms=round(latency, 2),
                    error_message=f"Permanent hard bounce: mailbox does not exist {recipient}",
                    retryable=False,
                )

            # Simulated successful transmission
            msg_id = f"ses-mock-{uuid.uuid4().hex[:12]}"
            latency = (time.perf_counter() - start_time) * 1000 + 25.0
            logger.info(f"[Mock SES] Delivered email to {recipient} (subject: '{subject}') [MsgID: {msg_id}]")
            return ProviderResult(
                status=NotificationStatus.DELIVERED,
                provider_name=provider_name,
                provider_message_id=msg_id,
                status_code=200,
                latency_ms=round(latency, 2),
                raw_response={"MessageId": msg_id, "Status": "Delivered"},
            )

        # Real AWS SES Delivery
        try:
            client = self._get_ses_client()
            response = client.send_email(
                Source=self.sender,
                Destination={"ToAddresses": [recipient]},
                Message={
                    "Subject": {"Data": subject or "Notification", "Charset": "UTF-8"},
                    "Body": {
                        "Html": {"Data": content, "Charset": "UTF-8"},
                        "Text": {"Data": content, "Charset": "UTF-8"},
                    },
                },
            )
            latency = (time.perf_counter() - start_time) * 1000
            msg_id = response.get("MessageId", str(uuid.uuid4()))
            return ProviderResult(
                status=NotificationStatus.DELIVERED,
                provider_name="aws_ses",
                provider_message_id=msg_id,
                status_code=200,
                latency_ms=round(latency, 2),
                raw_response=response,
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            logger.error(f"AWS SES delivery failed: {e}")
            return ProviderResult(
                status=NotificationStatus.FAILED,
                provider_name="aws_ses",
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
        # In async context, execute via standard dispatch
        return self.send(recipient, subject, content, metadata)
