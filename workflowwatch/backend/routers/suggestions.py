"""WP-6: Pattern-based workflow suggestions."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ..services.pattern_service import (
    get_suggestions_for_timeline,
    recompute_patterns,
    score_events_against_workflows,
)
from ..services.timeline_service import get_timeline

router = APIRouter(prefix="/api/v1/suggestions", tags=["suggestions"])


class ScoreEventInput(BaseModel):
    app: str | None = None
    title: str | None = None
    url: str | None = None


class ScoreRequest(BaseModel):
    events: list[ScoreEventInput]


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
    suggestions = get_suggestions_for_timeline(timeline_events)
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
