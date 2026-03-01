"""
Auto-label endpoints (WP-7).
Handles bulk accept/dismiss of auto-generated workflow suggestions,
and exposes cache stats.
"""

import logging
from collections import defaultdict
from datetime import date as date_type

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..models import (
    AutoLabelAcceptBody,
    AutoLabelDismissBody,
    AutoLabelStats,
    SessionCreate,
    SessionEventRef,
)
from ..services import cache_service
from ..services.signature_service import event_signature
from ..services.session_service import create_session
from ..services.timeline_service import get_timeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auto-label", tags=["auto-label"])


def _err(msg: str, status: int = 400):
    return JSONResponse(status_code=status, content={"detail": msg})


@router.post("/accept")
async def accept_auto_labels(request: Request, body: AutoLabelAcceptBody):
    """
    Accept auto-label suggestions for a batch of events.
    Groups events by workflow_id and creates one session per workflow.
    Updates the label cache and embedding index for accepted signatures.
    """
    aw = request.app.state.aw_service
    embedding_service = request.app.state.embedding_service

    try:
        target_date = date_type.fromisoformat(body.date)
    except ValueError:
        return _err("Invalid date format, expected YYYY-MM-DD")

    if not body.accepts:
        return _err("accepts list is empty")

    # Fetch timeline once to resolve event data for signature computation
    timeline_events = await get_timeline(aw, target_date)
    by_ref = {(e.aw_bucket_id, e.aw_event_id): e for e in timeline_events}

    # Group accepted events by workflow_id
    groups: dict[str, list[SessionEventRef]] = defaultdict(list)
    for item in body.accepts:
        groups[item.workflow_id].append(
            SessionEventRef(aw_bucket_id=item.aw_bucket_id, aw_event_id=item.aw_event_id)
        )

    created_sessions = []
    errors = []

    for workflow_id, event_refs in groups.items():
        try:
            session_body = SessionCreate(
                workflow_id=workflow_id,
                date=body.date,
                events=event_refs,
            )
            session = await create_session(session_body, aw)
            created_sessions.append(session.id)

            # Update cache and embedding index for each accepted event
            for ref in event_refs:
                key = (ref.aw_bucket_id, ref.aw_event_id)
                event = by_ref.get(key)
                if event:
                    sig = event_signature(event.data)
                    cache_service.record_hit(sig, workflow_id)
                    embedding_service.add(sig, workflow_id)

        except ValueError as exc:
            msg = str(exc)
            if "already labeled" in msg:
                # Skip already-labeled events silently (idempotent)
                logger.debug("Skipping already-labeled events for workflow %s", workflow_id)
            else:
                errors.append({"workflow_id": workflow_id, "error": msg})

    return {
        "created_sessions": len(created_sessions),
        "errors": errors,
    }


@router.post("/dismiss")
async def dismiss_auto_labels(request: Request, body: AutoLabelDismissBody):
    """
    Record negative signals for dismissed auto-label suggestions.
    After DISMISSAL_THRESHOLD dismissals, the suggestion is suppressed.
    """
    aw = request.app.state.aw_service

    try:
        target_date = date_type.fromisoformat(body.date)
    except ValueError:
        return _err("Invalid date format, expected YYYY-MM-DD")

    if not body.dismissals:
        return _err("dismissals list is empty")

    # Resolve signatures for events that didn't include them
    need_resolve = [d for d in body.dismissals if not d.signature]
    resolved_sigs: dict[tuple[str, int], str] = {}
    if need_resolve:
        timeline_events = await get_timeline(aw, target_date)
        by_ref = {(e.aw_bucket_id, e.aw_event_id): e for e in timeline_events}
        for item in need_resolve:
            key = (item.aw_bucket_id, item.aw_event_id)
            event = by_ref.get(key)
            if event:
                resolved_sigs[key] = event_signature(event.data)

    count = 0
    for item in body.dismissals:
        sig = item.signature or resolved_sigs.get((item.aw_bucket_id, item.aw_event_id))
        if not sig:
            continue
        cache_service.record_dismissal(sig, item.workflow_id)
        count += 1

    return {"dismissed": count}


@router.get("/stats", response_model=AutoLabelStats)
async def auto_label_stats(request: Request):
    """Return label cache statistics."""
    embedding_service = request.app.state.embedding_service
    stats = cache_service.get_cache_stats()
    return AutoLabelStats(
        cache_entries=stats["total_entries"],
        workflows_covered=stats["workflows_covered"],
        dismissals=stats["dismissals"],
        embedding_available=embedding_service.is_available,
    )


@router.post("/rebuild-cache")
async def rebuild_cache():
    """Force repopulate label cache from all session_events. Useful after import."""
    count = cache_service.populate_from_sessions()
    return {"status": "ok", "entries": count}
