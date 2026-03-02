"""WP-6: Pattern-based workflow suggestions."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..services.pattern_service import (
    dismiss_pattern_suggestion_event,
    dismiss_pattern_suggestions,
    get_suggestions_for_timeline,
    recompute_patterns,
    score_events_against_workflows,
)
from ..services.timeline_service import get_timeline

router = APIRouter(prefix="/api/v1/suggestions", tags=["suggestions"])


def _err(msg: str, status: int = 400):
    return JSONResponse(status_code=status, content={"detail": msg})


class ScoreEventInput(BaseModel):
    app: str | None = None
    title: str | None = None
    url: str | None = None


class ScoreRequest(BaseModel):
    events: list[ScoreEventInput]


class SuggestionEventRef(BaseModel):
    aw_bucket_id: str
    aw_event_id: int


class SuggestionDismissItem(BaseModel):
    workflow_id: str
    event_refs: list[SuggestionEventRef]


class SuggestionDismissRequest(BaseModel):
    date: str  # YYYY-MM-DD
    dismissals: list[SuggestionDismissItem]


class SuggestionDismissEventRequest(BaseModel):
    date: str  # YYYY-MM-DD
    workflow_id: str
    event_ref: SuggestionEventRef


@router.get("")
async def get_suggestions(request: Request, date: str):
    """
    Get pattern-based suggestions for a date.
    Fetches timeline, splits unlabeled events into blocks, scores each block
    against workflow patterns; returns suggestions where block has >= 2 matching indicators.
    """
    aw = request.app.state.aw_service
    from datetime import date as date_type
    target = date_type.fromisoformat(date)
    timeline_events = await get_timeline(aw, target)
    suggestions = get_suggestions_for_timeline(timeline_events, date=date)
    return {"date": date, "suggestions": suggestions}


@router.post("/score")
def post_score(body: ScoreRequest):
    """
    Score a list of events (app, title, url) against workflow patterns.
    Returns ranked workflows with score and matched_indicators.
    Used to pre-select workflow in "Label as…" dropdown.
    """
    events = [e.model_dump() for e in body.events]
    results = score_events_against_workflows(events)
    return {"ranked": results}


@router.post("/recompute")
def post_recompute():
    """Force recompute workflow patterns from current session_events."""
    recompute_patterns()
    return {"status": "ok"}


@router.post("/dismiss")
def post_dismiss(body: SuggestionDismissRequest):
    """Dismiss one or more pattern suggestions for a date."""
    from datetime import date as date_type
    try:
        date_type.fromisoformat(body.date)
    except ValueError:
        return _err("Invalid date format, expected YYYY-MM-DD")

    if not body.dismissals:
        return {"dismissed": 0}

    dismissed = dismiss_pattern_suggestions(
        body.date,
        [item.model_dump() for item in body.dismissals],
    )
    return {"dismissed": dismissed}


@router.post("/dismiss-event")
def post_dismiss_event(body: SuggestionDismissEventRequest):
    """Dismiss a single event for one workflow pattern suggestion (date-scoped)."""
    from datetime import date as date_type
    try:
        date_type.fromisoformat(body.date)
    except ValueError:
        return _err("Invalid date format, expected YYYY-MM-DD")

    dismissed = dismiss_pattern_suggestion_event(
        body.date,
        body.workflow_id,
        body.event_ref.model_dump(),
    )
    return {"dismissed": dismissed}
