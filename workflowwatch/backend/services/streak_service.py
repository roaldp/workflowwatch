"""
Daily streak & XP tracking service.
XP = total number of events labeled (lifetime).
Streak = consecutive days where at least 1 event was labeled.
"""

import logging
from datetime import date, datetime, timedelta, timezone

from ..database import get_db
from ..models import StreakData

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_total_xp() -> int:
    """Total lifetime XP = count of all session_events."""
    db = get_db()
    row = db.execute("SELECT COUNT(*) FROM session_events").fetchone()
    return row[0] if row else 0


def get_today_xp(target_date: date) -> int:
    """Events labeled on a specific date."""
    db = get_db()
    row = db.execute(
        "SELECT events_labeled FROM daily_progress WHERE date = ?",
        (target_date.isoformat(),),
    ).fetchone()
    return row[0] if row else 0


def get_streak(as_of: date) -> int:
    """
    Count consecutive days with events_labeled > 0, walking backward from as_of.
    Today counts if at least 1 event was labeled today.
    """
    db = get_db()
    rows = db.execute(
        "SELECT date, events_labeled FROM daily_progress WHERE events_labeled > 0 ORDER BY date DESC"
    ).fetchall()

    if not rows:
        return 0

    # Build a set of active dates
    active_dates = {row["date"] for row in rows}

    streak = 0
    current = as_of
    while current.isoformat() in active_dates:
        streak += 1
        current -= timedelta(days=1)

    return streak


def get_streak_data(target_date: date) -> StreakData:
    """Aggregate streak info for a given date."""
    return StreakData(
        date=target_date.isoformat(),
        total_xp=get_total_xp(),
        today_xp=get_today_xp(target_date),
        current_streak=get_streak(target_date),
    )


def increment_daily_progress(target_date: date, count: int = 1) -> None:
    """Increment the events_labeled counter for a date (upsert)."""
    if count <= 0:
        return
    db = get_db()
    now = _now_iso()
    db.execute(
        """
        INSERT INTO daily_progress (date, events_labeled, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            events_labeled = events_labeled + ?,
            updated_at = ?
        """,
        (target_date.isoformat(), count, now, count, now),
    )
    db.commit()


def decrement_daily_progress(target_date: date, count: int = 1) -> None:
    """Decrement the events_labeled counter for a date (floor at 0)."""
    if count <= 0:
        return
    db = get_db()
    now = _now_iso()
    db.execute(
        """
        UPDATE daily_progress
        SET events_labeled = MAX(0, events_labeled - ?),
            updated_at = ?
        WHERE date = ?
        """,
        (count, now, target_date.isoformat()),
    )
    db.commit()
