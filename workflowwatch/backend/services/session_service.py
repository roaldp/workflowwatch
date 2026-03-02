import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from ..database import get_db
from ..models import (
    Session,
    SessionCreate,
    SessionEventRef,
    SessionEventSnapshot,
    SessionUpdate,
    SessionWithEvents,
    TimelineEvent,
)
from . import cache_service
from .pattern_service import recompute_patterns
from .timeline_service import get_timeline
from .workflow_service import get_workflow

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_session(body: SessionCreate, aw) -> Session:
    """
    Create a session for the given workflow and event refs.
    Fetches timeline for body.date, matches refs to events, snapshots data, inserts session + session_events.
    Raises ValueError with a message for 400/404/409 cases.
    """
    from datetime import date

    target_date = date.fromisoformat(body.date)
    if not body.events:
        raise ValueError("events list is empty")

    workflow = get_workflow(body.workflow_id)
    if workflow is None or workflow.archived:
        raise ValueError("workflow not found or archived")

    db = get_db()
    placeholders = ",".join("(?,?)" for _ in body.events)
    params = [p for r in body.events for p in (r.aw_bucket_id, r.aw_event_id)]
    existing = db.execute(
        f"""
        SELECT aw_bucket_id, aw_event_id FROM session_events
        WHERE (aw_bucket_id, aw_event_id) IN ({placeholders})
        """,
        params,
    ).fetchall()
    if existing:
        already = [f"{r[0]}:{r[1]}" for r in existing]
        raise ValueError(f"events already labeled: {already}")

    timeline_events = await get_timeline(aw, target_date)
    by_ref = {(e.aw_bucket_id, e.aw_event_id): e for e in timeline_events}

    matched: list[TimelineEvent] = []
    for ref in body.events:
        key = (ref.aw_bucket_id, ref.aw_event_id)
        if key not in by_ref:
            raise ValueError(f"event not found in timeline: {ref.aw_bucket_id}:{ref.aw_event_id}")
        matched.append(by_ref[key])

    started_at = min(e.timestamp for e in matched)
    ended_at = max(
        e.timestamp + timedelta(seconds=e.duration) for e in matched
    )
    duration_seconds = sum(e.duration for e in matched)

    session_id = str(uuid.uuid4())
    now = _now_iso()

    db.execute(
        """
        INSERT INTO sessions (id, workflow_id, context_workflow_id, title, started_at, ended_at, duration, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            body.workflow_id,
            body.context_workflow_id,
            body.title,
            started_at.isoformat(),
            ended_at.isoformat(),
            duration_seconds,
            body.notes,
            now,
            now,
        ),
    )

    for ev in matched:
        se_id = str(uuid.uuid4())
        event_data_json = json.dumps(ev.data) if ev.data else None
        db.execute(
            """
            INSERT INTO session_events (id, session_id, aw_bucket_id, aw_event_id, event_timestamp, event_duration, event_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                se_id,
                session_id,
                ev.aw_bucket_id,
                ev.aw_event_id,
                ev.timestamp.isoformat(),
                ev.duration,
                event_data_json,
            ),
        )

    db.commit()

    recompute_patterns()
    # WP-7: update label cache with the newly created session's events
    from .signature_service import event_signature
    for ev in matched:
        sig = event_signature(ev.data)
        cache_service.record_hit(sig, body.workflow_id)

    row = db.execute(
        "SELECT * FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    return _row_to_session(row)


def _row_to_session(row) -> Session:
    keys = row.keys() if hasattr(row, "keys") else []
    return Session(
        id=row["id"],
        workflow_id=row["workflow_id"],
        context_workflow_id=row["context_workflow_id"] if "context_workflow_id" in keys else None,
        title=row["title"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        duration=row["duration"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def list_sessions(
    workflow_id: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Session]:
    """List sessions, optionally filtered by workflow and date range. Newest first."""
    db = get_db()
    conditions = []
    params: list = []
    if workflow_id is not None:
        conditions.append("workflow_id = ?")
        params.append(workflow_id)
    if start_date is not None:
        conditions.append("started_at >= ?")
        params.append(start_date.isoformat())
    if end_date is not None:
        conditions.append("started_at < ?")
        params.append((end_date + timedelta(days=1)).isoformat())
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    params.extend([limit, offset])
    rows = db.execute(
        f"SELECT * FROM sessions{where} ORDER BY started_at DESC LIMIT ? OFFSET ?",
        params,
    ).fetchall()
    return [_row_to_session(r) for r in rows]


def get_session(session_id: str) -> SessionWithEvents | None:
    """Get a session with its linked events and snapshot data."""
    db = get_db()
    row = db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if row is None:
        return None
    session = _row_to_session(row)
    event_rows = db.execute(
        "SELECT aw_bucket_id, aw_event_id, event_timestamp, event_duration, event_data FROM session_events WHERE session_id = ? ORDER BY event_timestamp",
        (session_id,),
    ).fetchall()
    events = []
    for er in event_rows:
        data = None
        if er["event_data"]:
            try:
                data = json.loads(er["event_data"])
            except (json.JSONDecodeError, TypeError):
                pass
        events.append(
            SessionEventSnapshot(
                aw_bucket_id=er["aw_bucket_id"],
                aw_event_id=er["aw_event_id"],
                event_timestamp=er["event_timestamp"],
                event_duration=er["event_duration"],
                event_data=data,
            )
        )
    return SessionWithEvents(
        **session.model_dump(),
        events=events,
    )


def update_session(session_id: str, body: SessionUpdate) -> Session | None:
    """Update session title/notes/context. Return updated session or None."""
    db = get_db()
    row = db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if row is None:
        return None
    updates = []
    params = []
    if body.title is not None:
        updates.append("title = ?")
        params.append(body.title)
    if body.notes is not None:
        updates.append("notes = ?")
        params.append(body.notes)
    if body.context_workflow_id is not None:
        updates.append("context_workflow_id = ?")
        # empty string means clear the context
        params.append(None if body.context_workflow_id == "" else body.context_workflow_id)
    if not updates:
        return _row_to_session(row)
    params.append(_now_iso())
    params.append(session_id)
    db.execute(
        f"UPDATE sessions SET {', '.join(updates)}, updated_at = ? WHERE id = ?",
        params,
    )
    db.commit()
    row = db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return _row_to_session(row)


def delete_session(session_id: str) -> bool:
    """Hard delete session and its session_events. Return True if deleted."""
    db = get_db()
    cur = db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    db.commit()
    return cur.rowcount > 0


def _recompute_session_times(db, session_id: str) -> None:
    """Update session started_at, ended_at, duration from its session_events."""
    rows = db.execute(
        "SELECT event_timestamp, event_duration FROM session_events WHERE session_id = ? ORDER BY event_timestamp",
        (session_id,),
    ).fetchall()
    if not rows:
        db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        db.commit()
        return
    started = datetime.fromisoformat(rows[0]["event_timestamp"].replace("Z", "+00:00"))
    duration_total = 0.0
    ended = started
    for r in rows:
        dur = r["event_duration"]
        duration_total += dur
        ts = datetime.fromisoformat(r["event_timestamp"].replace("Z", "+00:00"))
        end_ts = ts + timedelta(seconds=dur)
        if end_ts > ended:
            ended = end_ts
    db.execute(
        "UPDATE sessions SET started_at = ?, ended_at = ?, duration = ?, updated_at = ? WHERE id = ?",
        (started.isoformat(), ended.isoformat(), duration_total, _now_iso(), session_id),
    )
    db.commit()


async def add_events_to_session(
    session_id: str, event_refs: list[SessionEventRef], aw
) -> Session | None:
    """Add event refs to session; fetch from timeline, snapshot, recompute. Return updated session or None."""
    db = get_db()
    row = db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if row is None:
        return None
    if not event_refs:
        return _row_to_session(row)
    started_at = row["started_at"]
    target_date = date.fromisoformat(started_at[:10])
    placeholders = ",".join("(?,?)" for _ in event_refs)
    params = [p for r in event_refs for p in (r.aw_bucket_id, r.aw_event_id)]
    existing = db.execute(
        f"SELECT aw_bucket_id, aw_event_id FROM session_events WHERE (aw_bucket_id, aw_event_id) IN ({placeholders})",
        params,
    ).fetchall()
    if existing:
        raise ValueError("one or more events already belong to a session")
    timeline_events = await get_timeline(aw, target_date)
    by_ref = {(e.aw_bucket_id, e.aw_event_id): e for e in timeline_events}
    matched: list[TimelineEvent] = []
    for ref in event_refs:
        key = (ref.aw_bucket_id, ref.aw_event_id)
        if key not in by_ref:
            raise ValueError(f"event not found in timeline: {ref.aw_bucket_id}:{ref.aw_event_id}")
        matched.append(by_ref[key])
    for ev in matched:
        se_id = str(uuid.uuid4())
        event_data_json = json.dumps(ev.data) if ev.data else None
        db.execute(
            "INSERT INTO session_events (id, session_id, aw_bucket_id, aw_event_id, event_timestamp, event_duration, event_data) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (se_id, session_id, ev.aw_bucket_id, ev.aw_event_id, ev.timestamp.isoformat(), ev.duration, event_data_json),
        )
    db.commit()
    _recompute_session_times(db, session_id)
    row = db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return _row_to_session(row) if row else None


def remove_events_from_session(
    session_id: str, event_refs: list[SessionEventRef]
) -> Session | None:
    """Remove event refs from session; recompute; delete session if no events left. Return updated session or None if deleted."""
    db = get_db()
    row = db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if row is None:
        return None
    for ref in event_refs:
        db.execute(
            "DELETE FROM session_events WHERE session_id = ? AND aw_bucket_id = ? AND aw_event_id = ?",
            (session_id, ref.aw_bucket_id, ref.aw_event_id),
        )
    db.commit()
    _recompute_session_times(db, session_id)
    row = db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return _row_to_session(row) if row else None
