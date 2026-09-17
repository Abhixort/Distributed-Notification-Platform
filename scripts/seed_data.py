import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from sqlalchemy import select
from app.core.database import AsyncSessionLocal, init_db
from app.models.api_key import ApiKey
from app.models.template import Template
from app.schemas.enums import ChannelType


async def seed():
    print("Initializing database tables...")
    await init_db()

    async with AsyncSessionLocal() as db:
        # Check existing templates
        stmt = select(Template)
        existing_templates = (await db.execute(stmt)).scalars().all()

        if not existing_templates:
            print("Seeding notification templates...")
            templates = [
                Template(
                    name="welcome_email",
                    description="Standard welcome email sent after user onboarding",
                    channel=ChannelType.EMAIL.value,
                    subject_template="Welcome to {{ app_name }}, {{ user_name }}! 🎉",
                    body_template="<h1>Hello {{ user_name }}!</h1><p>Welcome to <strong>{{ app_name }}</strong>. Your account has been provisioned on cluster <code>{{ cluster_id }}</code>.</p><p><a href='{{ dashboard_url }}'>Access your dashboard</a></p>",
                    variables=["app_name", "user_name", "cluster_id", "dashboard_url"],
                ),
                Template(
                    name="security_otp_sms",
                    description="One-time passcode for two-factor authentication",
                    channel=ChannelType.SMS.value,
                    body_template="Your {{ app_name }} verification code is {{ otp_code }}. Valid for {{ valid_mins }} minutes. Do not share this with anyone.",
                    variables=["app_name", "otp_code", "valid_mins"],
                ),
                Template(
                    name="order_webhook",
                    description="Outbound webhook notification for order status lifecycle events",
                    channel=ChannelType.WEBHOOK.value,
                    body_template='{"order_id": "{{ order_id }}", "status": "{{ order_status }}", "amount_cents": {{ amount_cents }}, "currency": "{{ currency }}", "customer_id": "{{ customer_id }}"}',
                    variables=["order_id", "order_status", "amount_cents", "currency", "customer_id"],
                ),
                Template(
                    name="system_outage_alert",
                    description="High-priority system outage incident alert",
                    channel=ChannelType.EMAIL.value,
                    subject_template="🚨 CRITICAL: Service Incident on {{ service_name }}",
                    body_template="<h2>Incident Alert</h2><p>Service <strong>{{ service_name }}</strong> reported an anomaly: {{ incident_details }}.</p><p>Severity: <strong>{{ severity }}</strong></p>",
                    variables=["service_name", "incident_details", "severity"],
                ),
            ]
            db.add_all(templates)
            await db.commit()
            print(f"Seeded {len(templates)} templates successfully.")

        # Check existing API Keys
        k_stmt = select(ApiKey)
        existing_keys = (await db.execute(k_stmt)).scalars().all()
        if not existing_keys:
            print("Seeding default API Keys...")
            api_keys = [
                ApiKey(
                    key_hash="notif_master_key_super_secret_9999",
                    name="Platform Master Admin Key",
                    client_id="master_admin",
                    rate_limit_capacity=1000,
                    rate_limit_refill_rate=500.0,
                ),
                ApiKey(
                    key_hash="client_ecommerce_tier1_secret_key",
                    name="E-Commerce Microservice Key",
                    client_id="ecommerce_service",
                    rate_limit_capacity=300,
                    rate_limit_refill_rate=200.0,
                ),
            ]
            db.add_all(api_keys)
            await db.commit()
            print(f"Seeded {len(api_keys)} API keys successfully.")

    print("Database seeding completed!")


if __name__ == "__main__":
    asyncio.run(seed())
