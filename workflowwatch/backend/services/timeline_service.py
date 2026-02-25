import logging
from datetime import date, datetime, timedelta, timezone

from ..database import get_db
from ..models import TimelineEvent
from .aw_service import AWService

logger = logging.getLogger(__name__)


def _parse_timestamp(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp string into a timezone-aware datetime."""
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _filter_afk(events: list[dict], afk_events: list[dict]) -> list[dict]:
    """
    Keep only events whose midpoint falls within a not-afk period.

    This is the v1 simplified approach described in the workplan. A proper
    period-intersection implementation can replace this later.
    """
    not_afk_periods: list[tuple[datetime, datetime]] = []
    for ae in afk_events:
        status = ae.get("data", {}).get("status", "")
        if status == "not-afk":
            start = _parse_timestamp(ae["timestamp"])
            end = start + timedelta(seconds=ae.get("duration", 0))
            not_afk_periods.append((start, end))

    if not not_afk_periods:
        return events

    not_afk_periods.sort(key=lambda p: p[0])

    filtered: list[dict] = []
    for ev in events:
        ev_start = _parse_timestamp(ev["timestamp"])
        ev_dur = ev.get("duration", 0)
        midpoint = ev_start + timedelta(seconds=ev_dur / 2)

        for naf_start, naf_end in not_afk_periods:
            if naf_start <= midpoint <= naf_end:
                filtered.append(ev)
                break

    return filtered


async def get_timeline(aw: AWService, target_date: date) -> list[TimelineEvent]:
    """
    Build a unified timeline for a single day:
    1. Fetch window + browser + AFK events from AW.
    2. Filter out AFK periods.
    3. Annotate with session labels from our database.
    """
    if not await aw.ensure_connected():
        return []

    start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    raw_events: list[dict] = []

    if aw.bucket_info.window:
        window_events = await aw.get_events(aw.bucket_info.window, start, end)
        for ev in window_events:
            ev["_bucket"] = aw.bucket_info.window
        raw_events.extend(window_events)

    for browser_bid in aw.bucket_info.browser:
        browser_events = await aw.get_events(browser_bid, start, end)
        for ev in browser_events:
            ev["_bucket"] = browser_bid
        raw_events.extend(browser_events)

    afk_events: list[dict] = []
    if aw.bucket_info.afk:
        afk_events = await aw.get_events(aw.bucket_info.afk, start, end)

    raw_events.sort(key=lambda e: _parse_timestamp(e["timestamp"]))
    filtered_events = _filter_afk(raw_events, afk_events)

    db = get_db()
    labeled: dict[tuple[str, int], dict] = {}
    rows = db.execute(
        """
        SELECT se.aw_bucket_id, se.aw_event_id, se.session_id,
               w.name AS workflow_name, w.color AS workflow_color
        FROM session_events se
        JOIN sessions s ON se.session_id = s.id
        JOIN workflows w ON s.workflow_id = w.id
        WHERE se.event_timestamp >= ? AND se.event_timestamp < ?
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    for row in rows:
        key = (row["aw_bucket_id"], row["aw_event_id"])
        labeled[key] = {
            "session_id": row["session_id"],
            "workflow_name": row["workflow_name"],
            "workflow_color": row["workflow_color"],
        }

    timeline: list[TimelineEvent] = []
    for ev in filtered_events:
        bucket_id = ev.pop("_bucket", "unknown")
        event_id = ev.get("id", 0)
        label = labeled.get((bucket_id, event_id), {})

        data = ev.get("data", {})
        duration = ev.get("duration", 0)
        timestamp = _parse_timestamp(ev["timestamp"])

        timeline.append(
            TimelineEvent(
                aw_bucket_id=bucket_id,
                aw_event_id=event_id,
                timestamp=timestamp,
                duration=duration,
                data=data,
                session_id=label.get("session_id"),
                workflow_name=label.get("workflow_name"),
                workflow_color=label.get("workflow_color"),
            )
        )

    return timeline
