"""
Label rules service — Tier 0 of the auto-labeling pipeline.

User-defined deterministic rules:
  - 'app'           : match exact app name (case-insensitive)
  - 'title_keyword' : match substring in window title (case-insensitive)

Rules are applied before cache and embedding lookups, giving them highest
priority. Events matched by a rule are surfaced as suggestions with
source="rule" and confidence="high".
"""

import uuid
from datetime import datetime, timezone

from ..database import get_db
from ..models import TimelineEvent


def get_rules() -> list[dict]:
    db = get_db()
    rows = db.execute(
        """
        SELECT r.id, r.workflow_id, r.rule_type, r.match_value, r.created_at,
               w.name AS workflow_name, w.color AS workflow_color
        FROM label_rules r
        JOIN workflows w ON w.id = r.workflow_id
        WHERE w.archived = 0
        ORDER BY r.created_at
        """
    ).fetchall()
    return [dict(row) for row in rows]


def create_rule(workflow_id: str, rule_type: str, match_value: str) -> dict:
    db = get_db()
    # Return existing if duplicate
    existing = db.execute(
        "SELECT id FROM label_rules WHERE workflow_id=? AND rule_type=? AND match_value=?",
        (workflow_id, rule_type, match_value),
    ).fetchone()
    if existing:
        row = db.execute(
            """
            SELECT r.id, r.workflow_id, r.rule_type, r.match_value, r.created_at,
                   w.name AS workflow_name, w.color AS workflow_color
            FROM label_rules r
            JOIN workflows w ON w.id = r.workflow_id
            WHERE r.id = ?
            """,
            (existing["id"],),
        ).fetchone()
        return dict(row)

    rule_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT INTO label_rules (id, workflow_id, rule_type, match_value, created_at) VALUES (?,?,?,?,?)",
        (rule_id, workflow_id, rule_type, match_value, now),
    )
    db.commit()

    row = db.execute(
        """
        SELECT r.id, r.workflow_id, r.rule_type, r.match_value, r.created_at,
               w.name AS workflow_name, w.color AS workflow_color
        FROM label_rules r
        JOIN workflows w ON w.id = r.workflow_id
        WHERE r.id = ?
        """,
        (rule_id,),
    ).fetchone()
    return dict(row)


def delete_rule(rule_id: str) -> bool:
    db = get_db()
    cur = db.execute("DELETE FROM label_rules WHERE id=?", (rule_id,))
    db.commit()
    return cur.rowcount > 0


def apply_rules(
    events: list[TimelineEvent],
) -> dict[tuple[str, int], tuple[str, str, str]]:
    """
    Apply user-defined rules to unlabeled events.

    Returns dict of (aw_bucket_id, aw_event_id) → (workflow_id, workflow_name, explanation)
    for events matched by a rule. Already-labeled events are skipped.
    """
    rules = get_rules()
    if not rules:
        return {}

    results: dict[tuple[str, int], tuple[str, str, str]] = {}
    for event in events:
        if event.session_id is not None:
            continue
        data = event.data or {}
        app = (data.get("app") or "").lower().strip()
        title = (data.get("title") or "").lower().strip()

        for rule in rules:
            mv = rule["match_value"].lower().strip()
            rt = rule["rule_type"]
            wf_id = rule["workflow_id"]
            wf_name = rule["workflow_name"]

            if rt == "app" and app == mv:
                key = (event.aw_bucket_id, event.aw_event_id)
                results[key] = (
                    wf_id,
                    wf_name,
                    f"Rule: app '{rule['match_value']}' → {wf_name}",
                )
                break
            elif rt == "title_keyword" and mv and mv in title:
                key = (event.aw_bucket_id, event.aw_event_id)
                results[key] = (
                    wf_id,
                    wf_name,
                    f"Rule: title contains '{rule['match_value']}' → {wf_name}",
                )
                break

    return results
