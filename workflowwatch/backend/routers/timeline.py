import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request

from ..models import HealthResponse, TimelineEvent
from ..services.timeline_service import get_timeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["timeline"])


@router.get("/timeline", response_model=list[TimelineEvent])
async def timeline(request: Request, date: date = Query(..., description="Date in YYYY-MM-DD format")):
    """Return a unified, AFK-filtered timeline of AW events for a given date."""
    aw = request.app.state.aw_service
    if not await aw.ensure_connected():
        raise HTTPException(
            status_code=503,
            detail="Cannot reach ActivityWatch server",
        )
    events = await get_timeline(aw, date)
    return events


@router.get("/health", response_model=HealthResponse)
async def health(request: Request):
    """Return server status, AW connectivity, and discovered buckets."""
    aw = request.app.state.aw_service
    connected = await aw.ensure_connected()
    return HealthResponse(
        status="ok",
        aw_connected=connected,
        aw_server_url=aw._client.base_url.__str__(),
        buckets=aw.bucket_info,
        db_path=request.app.state.db_path,
    )
