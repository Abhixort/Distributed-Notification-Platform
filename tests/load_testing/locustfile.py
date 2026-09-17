import random
import uuid
from locust import HttpUser, between, task


class NotificationPlatformUser(HttpUser):
    """
    Locust load generator simulating distributed clients submitting notifications
    across Email, SMS, and Webhook channels with mixed priorities.
    """
    wait_time = between(0.01, 0.05)  # High throughput simulation

    @task(5)
    def send_email_notification(self):
        user_id = random.randint(1000, 9999)
        payload = {
            "channel": "email",
            "recipient": f"loadtest_user_{user_id}@benchmark.internal",
            "priority": random.choice(["high", "medium", "low"]),
            "subject": f"Benchmarking Alert #{random.randint(1, 10000)}",
            "content": f"Automated load testing payload verifying high-throughput pipeline for user {user_id}.",
            "idempotency_key": f"idemp-email-{uuid.uuid4().hex[:12]}",
        }
        self.client.post("/api/v1/notifications", json=payload, name="/api/v1/notifications [Email]")

    @task(3)
    def send_sms_notification(self):
        phone_suffix = random.randint(1000000, 9999999)
        payload = {
            "channel": "sms",
            "recipient": f"+1555{phone_suffix}",
            "priority": "high",
            "content": f"Security verification OTP: {random.randint(100000, 999999)}",
            "idempotency_key": f"idemp-sms-{uuid.uuid4().hex[:12]}",
        }
        self.client.post("/api/v1/notifications", json=payload, name="/api/v1/notifications [SMS]")

    @task(2)
    def send_webhook_notification(self):
        payload = {
            "channel": "webhook",
            "recipient": "http://localhost:8000/api/v1/mock-webhook/receive",
            "priority": "medium",
            "content": f'{{"event": "payment_completed", "tx_id": "{uuid.uuid4().hex}"}}',
            "idempotency_key": f"idemp-webhook-{uuid.uuid4().hex[:12]}",
        }
        self.client.post("/api/v1/notifications", json=payload, name="/api/v1/notifications [Webhook]")

    @task(1)
    def send_batch_notifications(self):
        items = [
            {
                "channel": random.choice(["email", "sms"]),
                "recipient": f"batch_{random.randint(100, 999)}@benchmark.internal",
                "priority": "medium",
                "content": "Bulk notification stream item",
                "idempotency_key": f"batch-sub-{uuid.uuid4().hex[:10]}",
            }
            for _ in range(10)
        ]
        self.client.post("/api/v1/notifications/batch", json={"notifications": items}, name="/api/v1/notifications/batch")

    @task(1)
    def check_system_metrics(self):
        self.client.get("/api/v1/analytics/realtime", name="/api/v1/analytics/realtime")
