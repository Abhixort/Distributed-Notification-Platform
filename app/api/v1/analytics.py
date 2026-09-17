import time
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, verify_api_key
from app.core.config import settings
from app.core.redis import get_async_redis
from app.models.delivery_log import DeliveryLog
from app.models.notification import Notification
from app.schemas.analytics import ChannelMetric, RealtimeAnalyticsResponse, SystemHealthResponse
from app.schemas.enums import NotificationStatus

router = APIRouter(prefix="/analytics", tags=["Analytics & Health"])
START_TIME = time.time()


@router.get("/realtime", response_model=RealtimeAnalyticsResponse, summary="Real-time Platform Metrics")
async def get_realtime_metrics(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    # Total counts by status
    status_stmt = select(Notification.status, func.count(Notification.id)).group_by(Notification.status)
    status_rows = (await db.execute(status_stmt)).all()
    status_map = {row[0]: row[1] for row in status_rows}

    total_all = sum(status_map.values())
    delivered = status_map.get(NotificationStatus.DELIVERED.value, 0)
    failed = status_map.get(NotificationStatus.FAILED.value, 0)
    dlq = status_map.get(NotificationStatus.DLQ.value, 0)
    in_flight = status_map.get(NotificationStatus.QUEUED.value, 0) + status_map.get(NotificationStatus.PROCESSING.value, 0)

    overall_success_rate = round((delivered / max(1, delivered + failed + dlq)) * 100, 1)

    # Channel metrics
    channels = ["email", "sms", "webhook"]
    channel_breakdown = {}

    for ch in channels:
        ch_stmt = select(Notification.status, func.count(Notification.id)).where(Notification.channel == ch).group_by(Notification.status)
        ch_rows = (await db.execute(ch_stmt)).all()
        ch_map = {r[0]: r[1] for r in ch_rows}

        ch_tot = sum(ch_map.values())
        ch_deliv = ch_map.get(NotificationStatus.DELIVERED.value, 0)
        ch_fail = ch_map.get(NotificationStatus.FAILED.value, 0)
        ch_dlq = ch_map.get(NotificationStatus.DLQ.value, 0)
        ch_succ = round((ch_deliv / max(1, ch_deliv + ch_fail + ch_dlq)) * 100, 1)

        # Average latency
        lat_stmt = (
            select(func.avg(DeliveryLog.latency_ms))
            .join(Notification, DeliveryLog.notification_id == Notification.id)
            .where(Notification.channel == ch)
        )
        avg_lat = (await db.execute(lat_stmt)).scalar() or 0.0

        channel_breakdown[ch] = ChannelMetric(
            total_requested=ch_tot,
            delivered=ch_deliv,
            failed=ch_fail,
            dlq=ch_dlq,
            success_rate_percent=ch_succ,
            avg_latency_ms=round(float(avg_lat), 2),
        )

    # Queue depths from Redis
    queue_depths = {"high_priority": 0, "default_priority": 0, "low_priority": 0, "dead_letter_queue": dlq}
    try:
        import asyncio
        async def fetch_queue_depths():
            redis_client = await get_async_redis()
            return {
                "high_priority": await redis_client.llen("high_priority"),
                "default_priority": await redis_client.llen("default_priority"),
                "low_priority": await redis_client.llen("low_priority"),
                "dead_letter_queue": dlq,
            }
        queue_depths = await asyncio.wait_for(fetch_queue_depths(), timeout=0.15)
    except Exception:
        pass

    uptime = max(1.0, time.time() - START_TIME)
    current_throughput = round(delivered / uptime, 2)

    return RealtimeAnalyticsResponse(
        system_status="HEALTHY",
        total_notifications=total_all,
        total_delivered=delivered,
        total_failed=failed,
        total_in_dlq=dlq,
        total_in_flight=in_flight,
        overall_success_rate_percent=overall_success_rate,
        current_throughput_per_sec=current_throughput,
        channel_breakdown=channel_breakdown,
        queue_depths=queue_depths,
    )


@router.get("/health", response_model=SystemHealthResponse, summary="System Health Check")
async def health_check(
    db: AsyncSession = Depends(get_db),
):
    # Check Database
    db_status = "healthy"
    try:
        await db.execute(select(1))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    # Check Redis
    redis_status = "healthy"
    try:
        redis_client = await get_async_redis()
        await redis_client.ping()
    except Exception as e:
        redis_status = f"offline / in-memory fallback ({str(e)})"

    return SystemHealthResponse(
        status="UP" if db_status == "healthy" else "DEGRADED",
        database=db_status,
        redis=redis_status,
        celery_broker=redis_status,
        version="1.0.0",
        uptime_seconds=round(time.time() - START_TIME, 2),
    )
