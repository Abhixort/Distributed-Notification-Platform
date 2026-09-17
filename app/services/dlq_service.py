from typing import Dict, List, Optional
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import ResourceNotFoundException
from app.core.logging import logger
from app.models.notification import Notification
from app.schemas.enums import ChannelType, NotificationStatus
from app.tasks.notification_tasks import redrive_dlq_task


class DLQService:
    """Dead Letter Queue (DLQ) Management, Analytics & Redrive Service."""

    @staticmethod
    async def get_dlq_items(
        db: AsyncSession,
        channel: Optional[ChannelType] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Notification]:
        """Fetch notifications currently parked in DLQ."""
        query = select(Notification).where(Notification.status == NotificationStatus.DLQ.value)
        if channel:
            query = query.where(Notification.channel == channel.value)

        query = query.order_by(Notification.failed_at.desc().nullslast()).offset(offset).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_dlq_stats(db: AsyncSession) -> Dict:
        """Get aggregate statistics on dead-lettered tasks."""
        # Total count
        total_stmt = select(func.count(Notification.id)).where(Notification.status == NotificationStatus.DLQ.value)
        total_count = (await db.execute(total_stmt)).scalar() or 0

        # By channel
        channel_stmt = (
            select(Notification.channel, func.count(Notification.id))
            .where(Notification.status == NotificationStatus.DLQ.value)
            .group_by(Notification.channel)
        )
        channel_rows = (await db.execute(channel_stmt)).all()
        by_channel = {row[0]: row[1] for row in channel_rows}

        # By priority
        priority_stmt = (
            select(Notification.priority, func.count(Notification.id))
            .where(Notification.status == NotificationStatus.DLQ.value)
            .group_by(Notification.priority)
        )
        priority_rows = (await db.execute(priority_stmt)).all()
        by_priority = {row[0]: row[1] for row in priority_rows}

        # Oldest item timestamp
        oldest_stmt = (
            select(func.min(Notification.failed_at))
            .where(Notification.status == NotificationStatus.DLQ.value)
        )
        oldest_ts = (await db.execute(oldest_stmt)).scalar()

        return {
            "total_dlq_count": total_count,
            "by_channel": by_channel,
            "by_priority": by_priority,
            "oldest_item_timestamp": oldest_ts,
        }

    @staticmethod
    async def redrive_items(
        db: AsyncSession,
        notification_ids: Optional[List[str]] = None,
        channel: Optional[ChannelType] = None,
        limit: int = 100,
    ) -> List[str]:
        """Re-enqueue DLQ messages back to Celery workers with renewed retry quotas."""
        query = select(Notification.id).where(Notification.status == NotificationStatus.DLQ.value)

        if notification_ids:
            query = query.where(Notification.id.in_(notification_ids))
        if channel:
            query = query.where(Notification.channel == channel.value)

        query = query.limit(limit)
        result = await db.execute(query)
        target_ids = list(result.scalars().all())

        if not target_ids:
            return []

        # Dispatch async Celery redrive task
        redrive_dlq_task.delay(target_ids)
        logger.info(f"Triggered DLQ redrive for {len(target_ids)} notification(s)")
        return target_ids

    @staticmethod
    async def purge_items(
        db: AsyncSession,
        notification_ids: Optional[List[str]] = None,
        channel: Optional[ChannelType] = None,
    ) -> int:
        """Purge unrecoverable dead messages permanently from DLQ."""
        query = delete(Notification).where(Notification.status == NotificationStatus.DLQ.value)

        if notification_ids:
            query = query.where(Notification.id.in_(notification_ids))
        if channel:
            query = query.where(Notification.channel == channel.value)

        result = await db.execute(query)
        await db.commit()
        return result.rowcount


dlq_service = DLQService()
