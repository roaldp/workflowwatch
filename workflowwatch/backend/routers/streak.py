"""
Daily streak & swipe card endpoints.
"""

import logging
from datetime import date as date_type

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from ..models import (
    SessionCreate,
    SessionEventRef,
    StreakData,
    SwipeActionBody,
    SwipeCardItem,
    SwipeCardQueue,
)
from ..services import cache_service
from ..services.auto_label_service import auto_label_events
from ..services.session_service import create_session
from ..services.signature_service import event_signature
from ..services.streak_service import get_streak_data
from ..services.timeline_service import get_timeline
from ..services.workflow_service import get_workflow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/streak", tags=["streak"])


def _err(msg: str, status: int = 400):
    return JSONResponse(status_code=status, content={"detail": msg})


@router.get("", response_model=StreakData)
async def streak_data(date: str = Query(..., description="YYYY-MM-DD")):
    """Return streak stats for a given date."""
    try:
        target_date = date_type.fromisoformat(date)
    except ValueError:
        return _err("Invalid date format, expected YYYY-MM-DD")
    return get_streak_data(target_date)


@router.get("/cards", response_model=SwipeCardQueue)
async def swipe_cards(
    request: Request,
    date: str = Query(..., description="YYYY-MM-DD"),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Build a swipe card queue from unlabeled events that have auto-label suggestions.
    High-confidence suggestions come first, then sorted by timestamp.
    """
    aw = request.app.state.aw_service
    embedding_service = request.app.state.embedding_service

    try:
        target_date = date_type.fromisoformat(date)
    except ValueError:
        return _err("Invalid date format, expected YYYY-MM-DD")

    timeline_events = await get_timeline(aw, target_date)
    unlabeled = [e for e in timeline_events if e.session_id is None]
    total_unlabeled = len(unlabeled)

    # Run auto-label pipeline to get suggestions
    auto_results = auto_label_events(unlabeled, embedding_service)

    # Build cards for events with suggestions
    cards: list[SwipeCardItem] = []
    for event in unlabeled:
        key = (event.aw_bucket_id, event.aw_event_id)
        result = auto_results.get(key)
        if result is None:
            continue

        wf = get_workflow(result.workflow_id)
        cards.append(SwipeCardItem(
            aw_bucket_id=event.aw_bucket_id,
            aw_event_id=event.aw_event_id,
            timestamp=event.timestamp,
            duration=event.duration,
            data=event.data,
            suggested_workflow_id=result.workflow_id,
            suggested_workflow_name=wf.name if wf else None,
            suggested_workflow_color=wf.color if wf else None,
            suggestion_confidence=result.confidence,
            suggestion_source=result.source,
        ))

    total_with_suggestions = len(cards)

    # Sort: high confidence first, then by timestamp
    confidence_order = {"high": 0, "medium": 1}
    cards.sort(key=lambda c: (confidence_order.get(c.suggestion_confidence, 2), c.timestamp))

    return SwipeCardQueue(
        date=date,
        cards=cards[:limit],
        total_unlabeled=total_unlabeled,
        total_with_suggestions=total_with_suggestions,
    )


@router.post("/accept")
async def accept_card(request: Request, body: SwipeActionBody):
    """
    Accept a swipe card: create a 1-event session and update caches.
    """
    aw = request.app.state.aw_service
    embedding_service = request.app.state.embedding_service

    try:
        target_date = date_type.fromisoformat(body.date)
    except ValueError:
        return _err("Invalid date format, expected YYYY-MM-DD")

    try:
        session_body = SessionCreate(
            workflow_id=body.workflow_id,
            date=body.date,
            events=[SessionEventRef(
                aw_bucket_id=body.aw_bucket_id,
                aw_event_id=body.aw_event_id,
            )],
        )
        session = await create_session(session_body, aw)

        # Update embedding index
        timeline_events = await get_timeline(aw, target_date)
        by_ref = {(e.aw_bucket_id, e.aw_event_id): e for e in timeline_events}
        event = by_ref.get((body.aw_bucket_id, body.aw_event_id))
        if event:
            sig = event_signature(event.data)
            embedding_service.add(sig, body.workflow_id)

        return {"session_id": session.id}

    except ValueError as exc:
        return _err(str(exc))


@router.post("/dismiss")
async def dismiss_card(request: Request, body: SwipeActionBody):
    """
    Dismiss a swipe card: record a negative signal for the suggestion.
    """
    aw = request.app.state.aw_service

    try:
        target_date = date_type.fromisoformat(body.date)
    except ValueError:
        return _err("Invalid date format, expected YYYY-MM-DD")

    # Resolve signature for the event
    timeline_events = await get_timeline(aw, target_date)
    by_ref = {(e.aw_bucket_id, e.aw_event_id): e for e in timeline_events}
    event = by_ref.get((body.aw_bucket_id, body.aw_event_id))
    if not event:
        return _err("Event not found in timeline", 404)

    sig = event_signature(event.data)
    cache_service.record_dismissal(sig, body.workflow_id)

    return {"dismissed": True}
