"""
Pattern-based workflow detection (WP-6).
Derives workflow patterns from labeled session_events and scores unlabeled blocks
by indicator co-occurrence (app+domain, domain+path, app+title).
"""

import json
import logging
import re
from collections import defaultdict
from urllib.parse import urlparse

from ..database import get_db

logger = logging.getLogger(__name__)

# Tuning (WP-6)
MIN_INDICATORS_MATCHED = 2
MIN_BLOCK_EVENTS = 2
MIN_BLOCK_DURATION_SECONDS = 60
MAX_GAP_MINUTES = 15
TITLE_KEY_MAX_LEN = 40


def _norm(s: str | None) -> str:
    if s is None or not isinstance(s, str):
        return ""
    return s.lower().strip()[:TITLE_KEY_MAX_LEN]


def _domain(url: str | None) -> str:
    if not url or not isinstance(url, str):
        return ""
    try:
        netloc = urlparse(url).netloc
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc.lower()
    except Exception:
        return ""


def _path_prefix(url: str | None) -> str:
    if not url or not isinstance(url, str):
        return ""
    try:
        path = urlparse(url).path
        parts = [p for p in path.split("/") if p][:2]
        return "/" + "/".join(parts) if parts else ""
    except Exception:
        return ""


def extract_indicators(data: dict | None) -> set[tuple[str, str, str]]:
    """
    Extract indicators from one event's data (app, title, url).
    Returns set of (indicator_type, value1, value2).
    """
    if not data or not isinstance(data, dict):
        return set()
    out = set()
    app = _norm(data.get("app"))
    title = _norm(data.get("title"))
    url = data.get("url") if isinstance(data.get("url"), str) else ""
    domain = _domain(url)
    path = _path_prefix(url)

    if app:
        if domain:
            out.add(("app_domain", app, domain))
        out.add(("app_title", app, title if title else "_"))
    if domain:
        if path:
            out.add(("domain_path", domain, path))
        elif title:
            out.add(("domain_path", domain, "t:" + title[:30]))
    return out


def _recompute_patterns() -> None:
    """Derive workflow patterns from session_events and store in workflow_patterns."""
    db = get_db()
    db.execute("DELETE FROM workflow_patterns")
    rows = db.execute(
        """
        SELECT s.workflow_id, s.id AS session_id, se.event_data
        FROM session_events se
        JOIN sessions s ON se.session_id = s.id
        WHERE se.event_data IS NOT NULL
        """
    ).fetchall()

    wf_sessions_indicators: dict[str, dict[str, set[tuple[str, str, str]]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for row in rows:
        wf_id = row["workflow_id"]
        session_id = row["session_id"]
        try:
            data = json.loads(row["event_data"]) if row["event_data"] else {}
        except (json.JSONDecodeError, TypeError):
            continue
        for ind in extract_indicators(data):
            wf_sessions_indicators[wf_id][session_id].add(ind)

    # Aggregate: for each workflow, count how many sessions had each indicator
    wf_indicator_counts: dict[str, dict[tuple[str, str, str], int]] = defaultdict(
        lambda: defaultdict(int)
    )
    for wf_id, sessions in wf_sessions_indicators.items():
        for _sid, indicators in sessions.items():
            for ind in indicators:
                wf_indicator_counts[wf_id][ind] += 1

    for wf_id, counts in wf_indicator_counts.items():
        for (itype, v1, v2), cnt in counts.items():
            if not v1:
                continue
            db.execute(
                """
                INSERT INTO workflow_patterns (workflow_id, indicator_type, value1, value2, session_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                (wf_id, itype, v1, v2 or "", cnt),
            )
    db.commit()
    logger.info("Recomputed workflow patterns for %d workflows", len(wf_indicator_counts))


def ensure_patterns() -> None:
    """Ensure workflow_patterns is populated (recompute if empty)."""
    db = get_db()
    n = db.execute("SELECT COUNT(*) FROM workflow_patterns").fetchone()[0]
    if n == 0:
        _recompute_patterns()


def recompute_patterns() -> None:
    """Force recompute workflow patterns from session_events."""
    _recompute_patterns()


def get_patterns_by_workflow() -> dict[str, list[tuple[str, str, str]]]:
    """Load workflow patterns from DB. Keys are workflow_id; values are list of (type, v1, v2)."""
    ensure_patterns()
    db = get_db()
    rows = db.execute(
        "SELECT workflow_id, indicator_type, value1, value2 FROM workflow_patterns"
    ).fetchall()
    out: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for r in rows:
        out[r["workflow_id"]].append(
            (r["indicator_type"], r["value1"], r["value2"] or "")
        )
    return dict(out)


def summarize_block(events: list[dict]) -> set[tuple[str, str, str]]:
    """Summarize a block of events (list of event data dicts) into a set of indicators."""
    out: set[tuple[str, str, str]] = set()
    for ev in events:
        data = ev if isinstance(ev, dict) else (ev.get("data") if hasattr(ev, "get") else {})
        if isinstance(ev, dict) and "data" in ev:
            data = ev["data"]
        out |= extract_indicators(data)
    return out


def _human_readable_indicator(itype: str, v1: str, v2: str) -> str:
    """Convert an indicator tuple into a human-readable description."""
    if itype == "app_title":
        title_part = v2 if v2 and v2 != "_" else "any title"
        return f'App "{v1}" with title "{title_part}"'
    if itype == "app_domain":
        return f'App "{v1}" on domain "{v2}"'
    if itype == "domain_path":
        if v2.startswith("t:"):
            return f'Domain "{v1}" with title "{v2[2:]}"'
        return f'Domain "{v1}" path "{v2}"'
    return f"{itype}: {v1} / {v2}"


def score_block_against_patterns(
    block_indicators: set[tuple[str, str, str]],
    patterns: dict[str, list[tuple[str, str, str]]],
    min_matched: int = MIN_INDICATORS_MATCHED,
) -> list[tuple[str, int, list[str]]]:
    """
    Score a block's indicators against each workflow pattern.
    Returns list of (workflow_id, score, matched_descriptions) sorted by score desc.
    Only includes workflows with score >= min_matched.
    """
    results: list[tuple[str, int, list[str]]] = []
    block_set = block_indicators
    for wf_id, ind_list in patterns.items():
        pattern_set = set(ind_list)
        matched = block_set & pattern_set
        score = len(matched)
        if score < min_matched:
            continue
        descs = [_human_readable_indicator(t, v1, v2) for t, v1, v2 in matched][:5]
        results.append((wf_id, score, descs))
    results.sort(key=lambda x: -x[1])
    return results


def score_events_against_workflows(
    events: list[dict],
    min_matched: int = MIN_INDICATORS_MATCHED,
) -> list[dict]:
    """
    Score a list of events (each with app/title/url or data) against workflow patterns.
    Returns list of { workflow_id, score, matched_indicators } for use in API.
    """
    ensure_patterns()
    patterns = get_patterns_by_workflow()
    if not patterns:
        return []
    block_indicators = summarize_block(events)
    scored = score_block_against_patterns(block_indicators, patterns, min_matched)
    return [
        {"workflow_id": wf_id, "score": score, "matched_indicators": descs}
        for wf_id, score, descs in scored
    ]


def _event_data(ev) -> dict:
    if hasattr(ev, "data"):
        return ev.data or {}
    if isinstance(ev, dict):
        return ev.get("data") or ev
    return {}


def _event_ref(ev) -> tuple[str, int]:
    if hasattr(ev, "aw_bucket_id"):
        return (ev.aw_bucket_id, ev.aw_event_id)
    if isinstance(ev, dict):
        return (ev["aw_bucket_id"], ev["aw_event_id"])
    return ("", 0)


def _event_ts(ev) -> float:
    if hasattr(ev, "timestamp"):
        t = ev.timestamp
        return t.timestamp() if hasattr(t, "timestamp") else 0
    if isinstance(ev, dict) and "timestamp" in ev:
        from datetime import datetime
        ts = ev["timestamp"]
        if isinstance(ts, (int, float)):
            return float(ts)
        if isinstance(ts, str):
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    return 0


def _event_duration(ev) -> float:
    if hasattr(ev, "duration"):
        return float(ev.duration)
    return float((ev or {}).get("duration", 0))


def get_suggestions_for_timeline(
    events: list,
    min_matched: int = MIN_INDICATORS_MATCHED,
    min_block_events: int = MIN_BLOCK_EVENTS,
    min_block_duration: float = MIN_BLOCK_DURATION_SECONDS,
    max_gap_minutes: float = MAX_GAP_MINUTES,
) -> list[dict]:
    """
    Split timeline into unlabeled blocks, score each against workflow patterns,
    return suggestions where block matches a pattern (>= min_matched indicators).
    """
    ensure_patterns()
    patterns = get_patterns_by_workflow()
    if not patterns:
        return []

    unlabeled = [
        e for e in events
        if (getattr(e, "session_id", None) or (e.get("session_id") if isinstance(e, dict) else None)) is None
    ]
    if not unlabeled:
        return []

    unlabeled_sorted = sorted(unlabeled, key=_event_ts)
    max_gap_sec = max_gap_minutes * 60
    blocks: list[list] = []
    current: list = []
    for ev in unlabeled_sorted:
        t = _event_ts(ev)
        if current and (t - _event_ts(current[-1]) - _event_duration(current[-1]) > max_gap_sec):
            if current:
                blocks.append(current)
            current = [ev]
        else:
            current.append(ev)
    if current:
        blocks.append(current)

    suggestions: list[dict] = []
    for block in blocks:
        if len(block) < min_block_events:
            continue
        total_dur = sum(_event_duration(e) for e in block)
        if total_dur < min_block_duration:
            continue
        data_list = [_event_data(e) for e in block]
        block_indicators = summarize_block(data_list)
        scored = score_block_against_patterns(block_indicators, patterns, min_matched)
        if not scored:
            continue
        wf_id, score, descs = scored[0]
        event_refs = [{"aw_bucket_id": _event_ref(e)[0], "aw_event_id": _event_ref(e)[1]} for e in block]
        suggestions.append({
            "type": "label",
            "workflow_id": wf_id,
            "event_refs": event_refs,
            "score": score,
            "matched_indicators": descs,
        })
    return suggestions
