from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, verify_api_key
from app.core.exceptions import (
    IdempotencyConflictException,
    RateLimitExceededException,
    ResourceNotFoundException,
    TemplateRenderError,
)
from app.schemas.enums import ChannelType, NotificationStatus, PriorityLevel
from app.schemas.notification import (
    NotificationBatchCreate,
    NotificationBatchResponse,
    NotificationCreate,
    NotificationFilter,
    NotificationResponse,
)
from app.services.notification_service import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.post(
    "",
    response_model=NotificationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Dispatch Single Notification",
    description="Asynchronously ingest and enqueue a multi-channel notification (Email, SMS, Webhook) with priority, token-bucket rate limiting, and idempotency protection.",
)
async def create_notification(
    payload: NotificationCreate,
    db: AsyncSession = Depends(get_db),
    client_id: str = Depends(verify_api_key),
):
    try:
        notification, is_new = await notification_service.create_notification(
            payload=payload,
            db=db,
            client_id=client_id,
        )
        return notification
    except RateLimitExceededException as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=e.message,
            headers={"Retry-After": str(int(e.retry_after) + 1)},
        )
    except IdempotencyConflictException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
        )
    except (ResourceNotFoundException, TemplateRenderError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )


@router.post(
    "/batch",
    response_model=NotificationBatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Dispatch High-Throughput Batch Notifications",
    description="Enqueue up to 1,000 notifications in a single atomic batch payload with bulk rate limit validation.",
)
async def create_batch_notifications(
    payload: NotificationBatchCreate,
    db: AsyncSession = Depends(get_db),
    client_id: str = Depends(verify_api_key),
):
    try:
        result = await notification_service.create_batch(
            batch_payload=payload,
            db=db,
            client_id=client_id,
        )
        return result
    except RateLimitExceededException as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=e.message,
            headers={"Retry-After": str(int(e.retry_after) + 1)},
        )


@router.get(
    "/{notification_id}",
    response_model=NotificationResponse,
    summary="Get Notification Details & Delivery Audit Log",
    description="Retrieve full details, delivery status, retry attempts, and downstream provider logs for a specific notification.",
)
async def get_notification(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    try:
        notification = await notification_service.get_notification_by_id(
            notification_id=notification_id,
            db=db,
        )
        return notification
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.get(
    "",
    response_model=List[NotificationResponse],
    summary="List Notifications",
    description="Filter and paginate notifications by channel, delivery status, priority level, or recipient.",
)
async def list_notifications(
    channel: Optional[ChannelType] = Query(None, description="Filter by notification channel"),
    status: Optional[NotificationStatus] = Query(None, description="Filter by status"),
    priority: Optional[PriorityLevel] = Query(None, description="Filter by priority level"),
    recipient: Optional[str] = Query(None, description="Search by recipient"),
    idempotency_key: Optional[str] = Query(None, description="Search by idempotency key"),
    limit: int = Query(50, ge=1, le=500, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    filter_params = NotificationFilter(
        channel=channel,
        status=status,
        priority=priority,
        recipient=recipient,
        idempotency_key=idempotency_key,
        limit=limit,
        offset=offset,
    )
    notifications, _ = await notification_service.list_notifications(filter_params=filter_params, db=db)
    return notifications
