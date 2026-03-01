from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from ..models import (
    Session,
    SessionCreate,
    SessionUpdate,
    SessionWithEvents,
    SessionEventsBody,
)
from ..services.session_service import (
    add_events_to_session,
    create_session,
    delete_session,
    get_session,
    list_sessions,
    remove_events_from_session,
    update_session,
)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def _err(msg: str, status: int):
    return JSONResponse(status_code=status, content={"detail": msg})


@router.get("", response_model=list[Session])
def get_sessions(
    workflow_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """List sessions, optionally filtered by workflow and date range. Newest first."""
    start_date = None
    end_date = None
    if start:
        try:
            start_date = date.fromisoformat(start)
        except ValueError:
            return _err("Invalid start date", 400)
    if end:
        try:
            end_date = date.fromisoformat(end)
        except ValueError:
            return _err("Invalid end date", 400)
    return list_sessions(
        workflow_id=workflow_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )


@router.get("/{session_id}", response_model=SessionWithEvents)
def get_one_session(session_id: str):
    """Get a session with its linked events."""
    s = get_session(session_id)
    if s is None:
        return _err("Session not found", 404)
    return s


@router.post("", response_model=Session, status_code=201)
async def post_session(request: Request, body: SessionCreate):
    """Create a session by labeling a set of timeline events with a workflow."""
    aw = request.app.state.aw_service
    try:
        return await create_session(body, aw)
    except ValueError as e:
        msg = str(e)
        if "workflow not found" in msg or "archived" in msg:
            return _err(msg, 404)
        if "already labeled" in msg:
            return _err(msg, 409)
        return _err(msg, 400)


@router.put("/{session_id}", response_model=Session)
def put_session(session_id: str, body: SessionUpdate):
    """Update session title and/or notes."""
    s = update_session(session_id, body)
    if s is None:
        return _err("Session not found", 404)
    return s


@router.delete("/{session_id}", status_code=204)
def delete_one_session(session_id: str):
    """Hard delete a session and its event links."""
    if not delete_session(session_id):
        return _err("Session not found", 404)
    return None


@router.post("/{session_id}/events", response_model=Session)
async def post_session_events(request: Request, session_id: str, body: SessionEventsBody):
    """Add events to a session. Recomputes session times."""
    aw = request.app.state.aw_service
    try:
        s = await add_events_to_session(session_id, body.events, aw)
        if s is None:
            return _err("Session not found", 404)
        return s
    except ValueError as e:
        msg = str(e)
        if "already belong" in msg:
            return _err(msg, 409)
        return _err(msg, 400)


@router.delete("/{session_id}/events")
def delete_session_events(session_id: str, body: SessionEventsBody):
    """Remove events from a session. Recomputes times; deletes session if no events left."""
    s = remove_events_from_session(session_id, body.events)
    if s is None:
        return Response(status_code=204)
    return s
