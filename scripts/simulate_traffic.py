import asyncio
import os
import random
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

API_BASE_URL = "http://localhost:8000/api/v1"

CHANNELS = [
    ("email", "dev@techcorp.io", "Deployment Successful", "All tests passed and build deployed."),
    ("email", "fail@techcorp.io", "Server Alert", "Simulating upstream error for retry & DLQ demonstration."),
    ("sms", "+15552345678", None, "Your security verification code is 849201."),
    ("webhook", "http://localhost:8000/api/v1/mock-webhook/receive", None, '{"event":"checkout_success","amount":99.0}'),
]

PRIORITIES = ["high", "medium", "low"]


async def send_traffic():
    print(">> Starting traffic simulation...")
    async with httpx.AsyncClient(timeout=10.0) as client:
        for i in range(1, 26):
            channel, recipient, subject, content = random.choice(CHANNELS)
            priority = random.choice(PRIORITIES)
            idempotency_key = f"traffic-{uuid.uuid4().hex[:10]}"

            payload = {
                "channel": channel,
                "recipient": recipient,
                "priority": priority,
                "subject": subject,
                "content": content,
                "idempotency_key": idempotency_key,
            }

            try:
                res = await client.post(f"{API_BASE_URL}/notifications", json=payload)
                if res.status_code == 202:
                    data = res.json()
                    print(f"[{i:02d}/25] Sent {channel.upper()} to {recipient} (Status: {data['status']}, Priority: {priority})")
                else:
                    print(f"[{i:02d}/25] {res.status_code}: {res.text}")
            except Exception as e:
                print(f"[{i:02d}/25] Connection error: {e}")

            await asyncio.sleep(0.3)

    print(">> Traffic simulation completed!")


if __name__ == "__main__":
    asyncio.run(send_traffic())
