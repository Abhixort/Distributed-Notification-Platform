from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, verify_api_key
from app.schemas.dlq import DLQItemResponse, DLQRedriveRequest, DLQRedriveResponse, DLQStatsResponse
from app.schemas.enums import ChannelType
from app.services.dlq_service import dlq_service

router = APIRouter(prefix="/dlq", tags=["Dead Letter Queue (DLQ)"])


@router.get("", response_model=List[DLQItemResponse], summary="List Dead-Lettered Notifications")
async def list_dlq_items(
    channel: Optional[ChannelType] = Query(None, description="Filter by channel"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    items = await dlq_service.get_dlq_items(db=db, channel=channel, limit=limit, offset=offset)
    return items


@router.get("/stats", response_model=DLQStatsResponse, summary="Get DLQ Aggregate Metrics")
async def get_dlq_stats(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    stats = await dlq_service.get_dlq_stats(db=db)
    return stats


@router.post("/redrive", response_model=DLQRedriveResponse, summary="Redrive / Retry Dead-Lettered Notifications")
async def redrive_dlq_items(
    payload: DLQRedriveRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    target_ids = await dlq_service.redrive_items(
        db=db,
        notification_ids=payload.notification_ids,
        channel=payload.channel,
        limit=payload.limit,
    )
    return DLQRedriveResponse(
        redriven_count=len(target_ids),
        message=f"Successfully queued {len(target_ids)} dead-lettered notification(s) for re-delivery.",
        notification_ids=target_ids,
    )


@router.delete("/purge", summary="Permanently Purge Unrecoverable Dead Notifications")
async def purge_dlq_items(
    channel: Optional[ChannelType] = Query(None, description="Purge by channel"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    purged_count = await dlq_service.purge_items(db=db, channel=channel)
    return {"purged_count": purged_count, "message": f"Successfully deleted {purged_count} dead notification(s)."}
