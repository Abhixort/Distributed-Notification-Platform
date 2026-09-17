from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.config import settings
from app.core.exceptions import (
    RateLimitExceededException,
    ResourceNotFoundException,
    TemplateRenderError,
)
from app.core.logging import logger
from app.core.metrics import NOTIFICATIONS_TOTAL
from app.models.delivery_log import DeliveryLog
from app.models.notification import Notification
from app.models.template import Template
from app.schemas.enums import ChannelType, NotificationStatus, PriorityLevel
from app.schemas.notification import NotificationBatchCreate, NotificationCreate, NotificationFilter
from app.services.idempotency import idempotency_service
from app.services.rate_limiter import rate_limiter
from app.services.template_service import template_service
from app.tasks.notification_tasks import batch_dispatch_chunk_task, dispatch_notification_task


class NotificationService:
    """Core orchestration service for notification ingestion, validation, rate limiting, and async dispatch."""

    @staticmethod
    async def create_notification(
        payload: NotificationCreate,
        db: AsyncSession,
        client_id: str = "default_client",
        bypass_rate_limit: bool = False,
    ) -> Tuple[Notification, bool]:
        """
        Ingests and queues a notification.
        Returns: (Notification, is_new: bool)
        """
        # 1. High-Throughput Token Bucket Rate Limit Check
        if not bypass_rate_limit:
            allowed, retry_after, remaining = await rate_limiter.check_rate_limit(
                client_id=client_id,
                channel=payload.channel.value,
                cost=1,
            )
            if not allowed:
                raise RateLimitExceededException(
                    retry_after=retry_after,
                    limit=settings.DEFAULT_RATE_LIMIT_CAPACITY,
                    remaining=remaining,
                )

        # 2. Dual-Tier Idempotency Check
        if payload.idempotency_key:
            is_new, existing = await idempotency_service.check_or_lock(
                idempotency_key=payload.idempotency_key,
                db_session=db,
            )
            if not is_new and existing:
                return existing, False

        try:
            # 3. Resolve Template if template_id is supplied
            rendered_subject = payload.subject
            rendered_content = payload.content

            if payload.template_id:
                # Query template by UUID or unique code
                t_stmt = select(Template).where(
                    (Template.id == payload.template_id) | (Template.name == payload.template_id)
                )
                t_res = await db.execute(t_stmt)
                tmpl = t_res.scalar_one_or_none()

                if not tmpl:
                    raise ResourceNotFoundException(f"Template '{payload.template_id}' not found.")

                subj, body = template_service.render_content(
                    body_template=tmpl.body_template,
                    subject_template=tmpl.subject_template or payload.subject,
                    data=payload.template_data,
                )
                rendered_subject = subj
                rendered_content = body

            # 4. Determine Initial Status
            is_scheduled = payload.scheduled_at and payload.scheduled_at > datetime.now(timezone.utc)
            initial_status = NotificationStatus.PENDING.value if is_scheduled else NotificationStatus.QUEUED.value

            # 5. Persist Notification to Database
            notification = Notification(
                channel=payload.channel.value,
                recipient=payload.recipient,
                priority=payload.priority.value,
                status=initial_status,
                subject=rendered_subject,
                content=rendered_content,
                template_id=payload.template_id,
                template_data=payload.template_data or {},
                idempotency_key=payload.idempotency_key,
                retry_count=0,
                max_retries=settings.MAX_NOTIFICATION_RETRIES,
                scheduled_at=payload.scheduled_at,
                notification_metadata=payload.metadata or {},
            )

            db.add(notification)
            await db.commit()
            await db.refresh(notification)

            # Record Ingestion Metric
            NOTIFICATIONS_TOTAL.labels(
                channel=notification.channel,
                priority=notification.priority,
                status="accepted",
            ).inc()

            # 6. Dispatch to Asynchronous Celery Queue if not scheduled for later
            if not is_scheduled:
                priority_map = {
                    PriorityLevel.HIGH.value: 9,
                    PriorityLevel.MEDIUM.value: 5,
                    PriorityLevel.LOW.value: 1,
                }
                queue_map = {
                    PriorityLevel.HIGH.value: "high_priority",
                    PriorityLevel.MEDIUM.value: "default_priority",
                    PriorityLevel.LOW.value: "low_priority",
                }

                priority_val = priority_map.get(notification.priority, 5)
                queue_name = queue_map.get(notification.priority, "default_priority")

                from app.core.redis import is_redis_available
                if is_redis_available():
                    try:
                        dispatch_notification_task.apply_async(
                            args=[notification.id],
                            queue=queue_name,
                            priority=priority_val,
                        )
                    except Exception as e:
                        logger.warning(f"Celery queue dispatch notice: {e}")
                else:
                    try:
                        dispatch_notification_task.apply(args=[notification.id])
                    except Exception as e:
                        logger.warning(f"Standalone execution notice: {e}")

            return notification, True

        finally:
            if payload.idempotency_key:
                await idempotency_service.release_lock(payload.idempotency_key)

    @staticmethod
    async def create_batch(
        batch_payload: NotificationBatchCreate,
        db: AsyncSession,
        client_id: str = "default_client",
    ) -> Dict[str, Any]:
        """High-Throughput Batch Ingestion supporting up to 1,000 notifications in a single call."""
        total = len(batch_payload.notifications)
        # Check bulk rate capacity
        allowed, retry_after, remaining = await rate_limiter.check_rate_limit(
            client_id=client_id,
            channel="batch",
            cost=min(total, 50),
        )
        if not allowed:
            raise RateLimitExceededException(retry_after=retry_after, limit=settings.DEFAULT_RATE_LIMIT_CAPACITY, remaining=remaining)

        queued_items: List[Notification] = []
        duplicate_count = 0
        failed_count = 0
        all_results: List[Notification] = []
        ids_to_dispatch: List[str] = []

        for item in batch_payload.notifications:
            try:
                notif, is_new = await NotificationService.create_notification(
                    payload=item,
                    db=db,
                    client_id=client_id,
                    bypass_rate_limit=True,
                )
                all_results.append(notif)
                if is_new:
                    queued_items.append(notif)
                    if not notif.scheduled_at:
                        ids_to_dispatch.append(notif.id)
                else:
                    duplicate_count += 1
            except Exception as e:
                logger.error(f"Error ingesting item in batch: {e}")
                failed_count += 1

        return {
            "total_requested": total,
            "queued_count": len(queued_items),
            "duplicate_count": duplicate_count,
            "failed_count": failed_count,
            "notifications": all_results,
        }

    @staticmethod
    async def get_notification_by_id(notification_id: str, db: AsyncSession) -> Notification:
        """Fetch notification by ID including nested delivery audit logs."""
        stmt = (
            select(Notification)
            .options(selectinload(Notification.logs))
            .where(Notification.id == notification_id)
        )
        result = await db.execute(stmt)
        notification = result.scalar_one_or_none()
        if not notification:
            raise ResourceNotFoundException(f"Notification '{notification_id}' not found.")
        return notification

    @staticmethod
    async def list_notifications(
        filter_params: NotificationFilter,
        db: AsyncSession,
    ) -> Tuple[List[Notification], int]:
        """List notifications with filtering and pagination."""
        query = select(Notification).options(selectinload(Notification.logs))

        if filter_params.channel:
            query = query.where(Notification.channel == filter_params.channel.value)
        if filter_params.status:
            query = query.where(Notification.status == filter_params.status.value)
        if filter_params.priority:
            query = query.where(Notification.priority == filter_params.priority.value)
        if filter_params.recipient:
            query = query.where(Notification.recipient.ilike(f"%{filter_params.recipient}%"))
        if filter_params.idempotency_key:
            query = query.where(Notification.idempotency_key == filter_params.idempotency_key)

        # Count total
        count_query = select(func.count()).select_from(query.order_by(None).subquery())
        total_count = (await db.execute(count_query)).scalar() or 0

        # Paginate
        query = query.order_by(Notification.created_at.desc()).offset(filter_params.offset).limit(filter_params.limit)
        result = await db.execute(query)
        notifications = list(result.scalars().all())

        return notifications, total_count


notification_service = NotificationService()
