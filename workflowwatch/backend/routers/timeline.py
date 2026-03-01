import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request

from ..models import HealthResponse, TimelineEvent
from ..services.timeline_service import get_timeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["timeline"])


@router.get("/timeline", response_model=list[TimelineEvent])
async def timeline(
    request: Request,
    date: date = Query(..., description="Date in YYYY-MM-DD format"),
    auto_label: bool = Query(False, description="Annotate unlabeled events with auto-label suggestions"),
):
    """Return a unified, AFK-filtered timeline of AW events for a given date."""
    aw = request.app.state.aw_service
    if not await aw.ensure_connected():
        raise HTTPException(
            status_code=503,
            detail="Cannot reach ActivityWatch server",
        )
    events = await get_timeline(aw, date)

    if auto_label:
        from ..services.auto_label_service import auto_label_events
        from ..services import cache_service
        from ..services.workflow_service import get_workflow

        embedding_service = request.app.state.embedding_service
        labels = auto_label_events(events, embedding_service)

        if labels:
            # Build workflow lookup for names/colors
            wf_cache: dict[str, tuple[str | None, str | None]] = {}

            def _wf_info(wf_id: str) -> tuple[str | None, str | None]:
                if wf_id not in wf_cache:
                    wf = get_workflow(wf_id)
                    wf_cache[wf_id] = (wf.name if wf else None, wf.color if wf else None)
                return wf_cache[wf_id]

            annotated: list[TimelineEvent] = []
            for event in events:
                key = (event.aw_bucket_id, event.aw_event_id)
                result = labels.get(key)
                if result and event.session_id is None:
                    wf_name, wf_color = _wf_info(result.workflow_id)
                    annotated.append(event.model_copy(update={
                        "suggested_workflow_id": result.workflow_id,
                        "suggested_workflow_name": wf_name,
                        "suggested_workflow_color": wf_color,
                        "suggestion_confidence": result.confidence,
                        "suggestion_source": result.source,
                        "suggestion_explanation": result.explanation,
                    }))
                else:
                    annotated.append(event)
            return annotated

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
