import random
import time
from datetime import datetime, timezone
from typing import List, Optional
from celery import shared_task
from sqlalchemy import select
from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import get_sync_db
from app.core.logging import logger
from app.core.metrics import (
    DELIVERY_LATENCY_SECONDS,
    DLQ_PUSHES_TOTAL,
    DLQ_REDRIVES_TOTAL,
    NOTIFICATIONS_DELIVERED,
)
from app.models.delivery_log import DeliveryLog
from app.models.notification import Notification
from app.providers.factory import provider_factory
from app.schemas.enums import NotificationStatus


@celery_app.task(
    bind=True,
    max_retries=settings.MAX_NOTIFICATION_RETRIES,
    name="app.tasks.notification_tasks.dispatch_notification_task",
)
def dispatch_notification_task(self, notification_id: str):
    """
    Main Celery Task for Asynchronous Multi-Channel Notification Delivery.
    Features exponential backoff with jitter and automated Dead-Letter Queue (DLQ) routing.
    """
    db_gen = get_sync_db()
    db = next(db_gen)

    try:
        # 1. Fetch Notification
        stmt = select(Notification).where(Notification.id == notification_id)
        notification = db.execute(stmt).scalar_one_or_none()

        if not notification:
            logger.error(f"Task aborted: Notification '{notification_id}' not found in database.")
            return {"status": "error", "message": "Notification not found"}

        if notification.status in [NotificationStatus.DELIVERED.value, NotificationStatus.DLQ.value]:
            logger.info(f"Skipping task for notification '{notification_id}', status already '{notification.status}'")
            return {"status": "skipped", "current_status": notification.status}

        # 2. Update Status to PROCESSING
        notification.status = NotificationStatus.PROCESSING.value
        db.commit()

        # 3. Resolve Delivery Provider
        provider = provider_factory.get_provider(notification.channel)

        # 4. Attempt Delivery
        start_time = time.perf_counter()
        result = provider.send(
            recipient=notification.recipient,
            subject=notification.subject,
            content=notification.content or "",
            metadata={
                **(notification.notification_metadata or {}),
                "notification_id": notification.id,
                "priority": notification.priority,
            },
        )
        duration = time.perf_counter() - start_time

        # 5. Record Audit Log
        attempt = notification.retry_count + 1
        log_entry = DeliveryLog(
            notification_id=notification.id,
            attempt_number=attempt,
            status=result.status.value,
            provider=result.provider_name,
            provider_message_id=result.provider_message_id,
            status_code=result.status_code,
            error_message=result.error_message,
            latency_ms=result.latency_ms,
        )
        db.add(log_entry)

        # 6. Handle Delivery Outcome
        if result.status == NotificationStatus.DELIVERED:
            notification.status = NotificationStatus.DELIVERED.value
            notification.delivered_at = datetime.now(timezone.utc)
            notification.error_details = None
            db.commit()

            # Record Prometheus metrics
            NOTIFICATIONS_DELIVERED.labels(
                channel=notification.channel,
                provider=result.provider_name,
                status="success",
            ).inc()
            DELIVERY_LATENCY_SECONDS.labels(
                channel=notification.channel,
                provider=result.provider_name,
            ).observe(duration)

            logger.info(f"Notification '{notification.id}' successfully delivered via {result.provider_name}")
            return {"status": "delivered", "notification_id": notification.id, "latency_ms": result.latency_ms}

        else:
            # Delivery Failed - Check Retry Eligibility
            notification.retry_count += 1
            notification.error_details = result.error_message

            NOTIFICATIONS_DELIVERED.labels(
                channel=notification.channel,
                provider=result.provider_name,
                status="failed",
            ).inc()

            if result.retryable and notification.retry_count < notification.max_retries:
                # Calculate Exponential Backoff with Jitter
                # Delay = Base * (Factor ^ attempt) + Random Jitter
                base_delay = settings.RETRY_BASE_DELAY_SECONDS
                factor = settings.RETRY_EXPONENTIAL_FACTOR
                jitter = random.uniform(0.1, 1.0)
                calculated_delay = min(
                    base_delay * (factor ** notification.retry_count) + jitter,
                    settings.RETRY_MAX_DELAY_SECONDS,
                )

                notification.status = NotificationStatus.QUEUED.value
                db.commit()

                logger.warning(
                    f"Notification '{notification.id}' delivery failed. Scheduling retry {notification.retry_count}/{notification.max_retries} in {calculated_delay:.2f}s"
                )

                # Retry task asynchronously
                raise self.retry(exc=Exception(result.error_message), countdown=int(calculated_delay))

            else:
                # Max retries exceeded or non-retryable error -> Push to Dead-Letter Queue (DLQ)
                notification.status = NotificationStatus.DLQ.value
                notification.failed_at = datetime.now(timezone.utc)
                db.commit()

                DLQ_PUSHES_TOTAL.labels(
                    channel=notification.channel,
                    reason="max_retries_exceeded" if result.retryable else "non_retryable_error",
                ).inc()

                logger.critical(
                    f"Notification '{notification.id}' exhausted retries ({notification.retry_count}/{notification.max_retries}). Transferred to Dead-Letter Queue (DLQ)."
                )

                return {
                    "status": "dlq",
                    "notification_id": notification.id,
                    "reason": result.error_message,
                    "retries": notification.retry_count,
                }

    except self.MaxRetriesExceededError:
        # Ensure status is DLQ if celery reaches MaxRetries
        stmt = select(Notification).where(Notification.id == notification_id)
        notification = db.execute(stmt).scalar_one_or_none()
        if notification:
            notification.status = NotificationStatus.DLQ.value
            notification.failed_at = datetime.now(timezone.utc)
            db.commit()
            DLQ_PUSHES_TOTAL.labels(channel=notification.channel, reason="celery_max_retries").inc()
        return {"status": "dlq", "notification_id": notification_id}

    except Exception as e:
        logger.exception(f"Unhandled exception processing notification '{notification_id}': {e}")
        db.rollback()
        raise e

    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


@celery_app.task(name="app.tasks.notification_tasks.batch_dispatch_chunk_task")
def batch_dispatch_chunk_task(notification_ids: List[str]):
    """High-Throughput task for dispatching chunks of notifications concurrently."""
    results = []
    for notif_id in notification_ids:
        res = dispatch_notification_task.apply_async(
            args=[notif_id],
            queue="high_priority",
            priority=8,
        )
        results.append({"notification_id": notif_id, "task_id": res.id})
    return {"dispatched_count": len(results), "tasks": results}


@celery_app.task(name="app.tasks.notification_tasks.process_scheduled_notifications")
def process_scheduled_notifications():
    """Celery Beat Cron: Ingest and dispatch notifications whose scheduled timestamp has arrived."""
    db_gen = get_sync_db()
    db = next(db_gen)
    now = datetime.now(timezone.utc)

    try:
        stmt = (
            select(Notification)
            .where(
                Notification.status == NotificationStatus.PENDING.value,
                Notification.scheduled_at <= now,
            )
            .limit(200)
        )
        notifications = db.execute(stmt).scalars().all()

        count = 0
        for notif in notifications:
            notif.status = NotificationStatus.QUEUED.value
            priority_val = 9 if notif.priority == "high" else (5 if notif.priority == "medium" else 1)
            queue_name = f"{notif.priority}_priority" if notif.priority in ["high", "low"] else "default_priority"

            dispatch_notification_task.apply_async(
                args=[notif.id],
                queue=queue_name,
                priority=priority_val,
            )
            count += 1

        db.commit()
        if count > 0:
            logger.info(f"Scheduled notifications cron: enqueued {count} notifications.")
        return {"processed": count}

    except Exception as e:
        logger.error(f"Error in process_scheduled_notifications cron: {e}")
        db.rollback()
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


@celery_app.task(name="app.tasks.notification_tasks.redrive_dlq_task")
def redrive_dlq_task(notification_ids: List[str]):
    """Re-enqueues dead-lettered notifications back to active priority queues."""
    db_gen = get_sync_db()
    db = next(db_gen)

    try:
        stmt = select(Notification).where(
            Notification.id.in_(notification_ids),
            Notification.status == NotificationStatus.DLQ.value,
        )
        notifications = db.execute(stmt).scalars().all()

        redriven = []
        for notif in notifications:
            notif.status = NotificationStatus.QUEUED.value
            notif.retry_count = 0  # Reset retry budget
            notif.failed_at = None
            notif.error_details = None

            priority_val = 9 if notif.priority == "high" else 5
            queue_name = "high_priority"  # Redrives are expedited

            dispatch_notification_task.apply_async(
                args=[notif.id],
                queue=queue_name,
                priority=priority_val,
            )
            DLQ_REDRIVES_TOTAL.labels(channel=notif.channel).inc()
            redriven.append(notif.id)

        db.commit()
        logger.info(f"Redrive task: Successfully re-enqueued {len(redriven)} notifications from DLQ.")
        return {"redriven_count": len(redriven), "notification_ids": redriven}

    except Exception as e:
        logger.error(f"Failed to redrive DLQ tasks: {e}")
        db.rollback()
        raise e
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass
