from fastapi import APIRouter
from app.api.v1.analytics import router as analytics_router
from app.api.v1.dlq import router as dlq_router
from app.api.v1.mock_webhook import router as mock_webhook_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.templates import router as templates_router

api_v1_router = APIRouter()

api_v1_router.include_router(notifications_router)
api_v1_router.include_router(templates_router)
api_v1_router.include_router(dlq_router)
api_v1_router.include_router(analytics_router)
api_v1_router.include_router(mock_webhook_router)
