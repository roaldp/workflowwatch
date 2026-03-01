"""
Label cache service (WP-7 Tier 1).
Maintains a SQLite lookup table mapping event signatures → workflow_id for instant labeling.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone

from ..database import get_db

logger = logging.getLogger(__name__)

# Dismissals threshold: after this many dismissals, stop suggesting
DISMISSAL_THRESHOLD = 2


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def populate_from_sessions() -> int:
    """
    Scan all session_events, compute signatures, populate label_cache.
    Uses majority vote when the same signature maps to multiple workflows.
    Returns number of cache entries written.
    """
    from .signature_service import event_signature

    db = get_db()

    rows = db.execute(
        """
        SELECT s.workflow_id, se.event_data
        FROM session_events se
        JOIN sessions s ON se.session_id = s.id
        WHERE se.event_data IS NOT NULL
        """
    ).fetchall()

    # sig → {workflow_id: count}
    sig_wf_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for row in rows:
        try:
            data = json.loads(row["event_data"]) if row["event_data"] else {}
        except (json.JSONDecodeError, TypeError):
            continue
        sig = event_signature(data)
        if sig and sig != "unknown||":
            sig_wf_counts[sig][row["workflow_id"]] += 1

    if not sig_wf_counts:
        return 0

    now = _now_iso()
    db.execute("DELETE FROM label_cache")

    count = 0
    for sig, wf_counts in sig_wf_counts.items():
        best_wf = max(wf_counts, key=lambda k: wf_counts[k])
        total_hits = sum(wf_counts.values())
        db.execute(
            """
            INSERT INTO label_cache (signature, workflow_id, hit_count, last_seen, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (sig, best_wf, total_hits, now, now),
        )
        count += 1

    db.commit()
    logger.info("Populated label cache with %d entries", count)
    return count


def lookup(signature: str) -> tuple[str, int] | None:
    """Look up a single signature. Returns (workflow_id, hit_count) or None."""
    if not signature:
        return None
    db = get_db()
    row = db.execute(
        "SELECT workflow_id, hit_count FROM label_cache WHERE signature = ?",
        (signature,),
    ).fetchone()
    if row is None:
        return None
    return (row["workflow_id"], row["hit_count"])


def bulk_lookup(signatures: list[str]) -> dict[str, str]:
    """
    Batch lookup signatures. Returns mapping of signature → workflow_id.
    Only returns hits; missing keys = no cache entry.
    """
    if not signatures:
        return {}
    db = get_db()
    placeholders = ",".join("?" for _ in signatures)
    rows = db.execute(
        f"SELECT signature, workflow_id FROM label_cache WHERE signature IN ({placeholders})",
        signatures,
    ).fetchall()
    return {row["signature"]: row["workflow_id"] for row in rows}


def record_hit(signature: str, workflow_id: str) -> None:
    """Upsert a cache entry, incrementing hit count on conflict."""
    if not signature or not workflow_id:
        return
    now = _now_iso()
    db = get_db()
    db.execute(
        """
        INSERT INTO label_cache (signature, workflow_id, hit_count, last_seen, created_at)
        VALUES (?, ?, 1, ?, ?)
        ON CONFLICT(signature) DO UPDATE SET
            workflow_id = excluded.workflow_id,
            hit_count = hit_count + 1,
            last_seen = excluded.last_seen
        """,
        (signature, workflow_id, now, now),
    )
    db.commit()


def invalidate_workflow(workflow_id: str) -> None:
    """Remove all cache entries for a workflow (on delete/archive)."""
    db = get_db()
    db.execute("DELETE FROM label_cache WHERE workflow_id = ?", (workflow_id,))
    db.commit()
    logger.info("Invalidated label cache for workflow %s", workflow_id)


def is_dismissed(signature: str, workflow_id: str) -> bool:
    """Return True if this (signature, workflow_id) was dismissed enough times."""
    if not signature or not workflow_id:
        return False
    db = get_db()
    row = db.execute(
        "SELECT count FROM label_dismissals WHERE signature = ? AND workflow_id = ?",
        (signature, workflow_id),
    ).fetchone()
    if row is None:
        return False
    return row["count"] >= DISMISSAL_THRESHOLD


def record_dismissal(signature: str, workflow_id: str) -> None:
    """Record a negative signal for a (signature, workflow_id) pair."""
    if not signature or not workflow_id:
        return
    now = _now_iso()
    db = get_db()
    db.execute(
        """
        INSERT INTO label_dismissals (signature, workflow_id, count, last_dismissed)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(signature, workflow_id) DO UPDATE SET
            count = count + 1,
            last_dismissed = excluded.last_dismissed
        """,
        (signature, workflow_id, now),
    )
    db.commit()


def get_cache_stats() -> dict:
    """Return cache statistics (used by health endpoint)."""
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM label_cache").fetchone()[0]
    workflows = db.execute("SELECT COUNT(DISTINCT workflow_id) FROM label_cache").fetchone()[0]
    dismissals = db.execute("SELECT COUNT(*) FROM label_dismissals").fetchone()[0]
    return {
        "total_entries": total,
        "workflows_covered": workflows,
        "dismissals": dismissals,
    }
