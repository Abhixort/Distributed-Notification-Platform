from celery import Celery
from kombu import Exchange, Queue
from app.core.config import settings

# Initialize Celery application
celery_app = Celery(
    "notification_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.notification_tasks",
    ],
)

# ---------------------------------------------------------------------------
# Kombu Exchanges & Queues Definition
# ---------------------------------------------------------------------------
default_exchange = Exchange("notifications", type="direct")
dlq_exchange = Exchange("notifications_dlq", type="direct")

celery_app.conf.update(
    # General Settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes hard limit
    task_soft_time_limit=240,  # 4 minutes soft limit
    task_acks_late=True,  # Guarantee delivery: ack only after task completes
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # Ensure fair task distribution across priority workers
    worker_max_tasks_per_child=1000,  # Prevent memory leaks
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_ignore_result=True,
    task_store_errors_even_if_ignored=False,
    broker_connection_retry_on_startup=False,
    broker_connection_max_retries=1,
    broker_connection_timeout=0.5,

    # Queues Configuration
    task_queues=(
        Queue("high_priority", default_exchange, routing_key="high_priority", queue_arguments={"x-max-priority": 10}),
        Queue("default_priority", default_exchange, routing_key="default_priority", queue_arguments={"x-max-priority": 10}),
        Queue("low_priority", default_exchange, routing_key="low_priority", queue_arguments={"x-max-priority": 10}),
        Queue("email_queue", default_exchange, routing_key="email_queue"),
        Queue("sms_queue", default_exchange, routing_key="sms_queue"),
        Queue("webhook_queue", default_exchange, routing_key="webhook_queue"),
        Queue("dead_letter_queue", dlq_exchange, routing_key="dead_letter_queue"),
    ),

    # Default Queue
    task_default_queue="default_priority",
    task_default_exchange="notifications",
    task_default_routing_key="default_priority",

    # Task Routing
    task_routes={
        "app.tasks.notification_tasks.dispatch_notification_task": {
            "queue": "default_priority",
            "routing_key": "default_priority",
        },
        "app.tasks.notification_tasks.batch_dispatch_chunk_task": {
            "queue": "high_priority",
            "routing_key": "high_priority",
        },
        "app.tasks.notification_tasks.redrive_dlq_task": {
            "queue": "high_priority",
            "routing_key": "high_priority",
        },
        "app.tasks.notification_tasks.process_scheduled_notifications": {
            "queue": "default_priority",
            "routing_key": "default_priority",
        },
    },

    # Celery Beat Scheduled Tasks
    beat_schedule={
        "check-scheduled-notifications-every-15-sec": {
            "task": "app.tasks.notification_tasks.process_scheduled_notifications",
            "schedule": 15.0,
        },
    },
)
