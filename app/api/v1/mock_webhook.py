import hashlib
import hmac
import time
from typing import Any, Dict
from fastapi import APIRouter, Header, HTTPException, Request, status
from app.core.config import settings
from app.core.logging import logger

router = APIRouter(prefix="/mock-webhook", tags=["Testing Utilities"])


@router.post("/receive", summary="Built-in Mock Webhook Target Endpoint")
async def receive_test_webhook(
    request: Request,
    x_notification_id: str = Header(None, alias="X-Notification-Id"),
    x_timestamp: str = Header(None, alias="X-Timestamp"),
    x_signature_sha256: str = Header(None, alias="X-Signature-SHA256"),
):
    """
    Simulated Webhook Receiver that verifies HMAC-SHA256 signatures
    and returns a success payload for testing and verification.
    """
    body_bytes = await request.body()

    # Verify HMAC signature if present
    if x_signature_sha256 and x_timestamp:
        sign_payload = f"{x_timestamp}.".encode("utf-8") + body_bytes
        expected_sig = hmac.new(
            settings.WEBHOOK_SECRET_KEY.encode("utf-8"),
            sign_payload,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(x_signature_sha256, expected_sig):
            logger.warning("Mock Webhook: Invalid HMAC Signature received!")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid HMAC signature",
            )

    logger.info(f"Mock Webhook endpoint received valid event {x_notification_id} ({len(body_bytes)} bytes)")
    return {
        "status": "success",
        "message": "Webhook payload received and signature verified successfully.",
        "notification_id": x_notification_id,
        "timestamp": x_timestamp,
    }
