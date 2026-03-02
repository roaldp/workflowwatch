import uuid
from datetime import date, datetime, timedelta, timezone

from ..database import get_db
from ..models import (
    Workflow,
    WorkflowBreakdownItem,
    WorkflowCompositionStep,
    WorkflowCompositionStepInput,
    WorkflowCreate,
    WorkflowStats,
    WorkflowUpdate,
)

DEFAULT_COLORS = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"]

# Seeded on first launch (when DB has no workflows at all)
_SEED_WORKFLOWS = [
    {"name": "Deep Work",     "color": "#6366F1", "description": "Focused coding, writing, or analysis — no interruptions"},
    {"name": "Research",      "color": "#8B5CF6", "description": "Reading, web research, and information gathering"},
    {"name": "Meetings",      "color": "#10B981", "description": "Calls, video meetings, and syncs"},
    {"name": "Email & Comms", "color": "#F59E0B", "description": "Email, Slack, and async communication"},
    {"name": "Admin",         "color": "#94A3B8", "description": "Calendar, scheduling, and operational tasks"},
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_workflows(include_archived: bool = False) -> list[Workflow]:
    """Return workflows, optionally including archived."""
    db = get_db()
    if include_archived:
        rows = db.execute("SELECT * FROM workflows ORDER BY name").fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM workflows WHERE archived = 0 ORDER BY name"
        ).fetchall()
    return [_row_to_workflow(r) for r in rows]


def create_workflow(body: WorkflowCreate) -> Workflow:
    """Create a workflow with UUID and timestamps. Assign default color if omitted."""
    db = get_db()
    wf_id = str(uuid.uuid4())
    now = _now_iso()
    color = body.color
    if not color:
        count = db.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]
        color = DEFAULT_COLORS[count % len(DEFAULT_COLORS)]
    db.execute(
        """
        INSERT INTO workflows (id, name, description, color, is_composite, created_at, updated_at, archived)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """,
        (wf_id, body.name, body.description or None, color, int(body.is_composite), now, now),
    )
    if body.is_composite and body.composition:
        _upsert_composition(db, wf_id, body.composition)
    db.commit()
    row = db.execute("SELECT * FROM workflows WHERE id = ?", (wf_id,)).fetchone()
    return _row_to_workflow(row)


def get_workflow(wf_id: str) -> Workflow | None:
    """Return a workflow by id or None."""
    db = get_db()
    row = db.execute("SELECT * FROM workflows WHERE id = ?", (wf_id,)).fetchone()
    if row is None:
        return None
    return _row_to_workflow(row)


def update_workflow(wf_id: str, body: WorkflowUpdate) -> Workflow | None:
    """Update workflow fields that are set. Return updated workflow or None if not found."""
    db = get_db()
    row = db.execute("SELECT * FROM workflows WHERE id = ?", (wf_id,)).fetchone()
    if row is None:
        return None
    updates = []
    params = []
    if body.name is not None:
        updates.append("name = ?")
        params.append(body.name)
    if body.description is not None:
        updates.append("description = ?")
        params.append(body.description)
    if body.color is not None:
        updates.append("color = ?")
        params.append(body.color)
    if updates:
        updates.append("updated_at = ?")
        params.append(_now_iso())
        params.append(wf_id)
        db.execute(
            f"UPDATE workflows SET {', '.join(updates)} WHERE id = ?",
            params,
        )
    if body.composition is not None:
        # Replace composition entirely ([] = clear)
        db.execute("DELETE FROM workflow_composition WHERE parent_id = ?", (wf_id,))
        if body.composition:
            _upsert_composition(db, wf_id, body.composition)
    db.commit()
    row = db.execute("SELECT * FROM workflows WHERE id = ?", (wf_id,)).fetchone()
    return _row_to_workflow(row)


def archive_workflow(wf_id: str) -> bool:
    """Set archived=1. Return True if a row was updated."""
    db = get_db()
    cur = db.execute(
        "UPDATE workflows SET archived = 1, updated_at = ? WHERE id = ?",
        (_now_iso(), wf_id),
    )
    db.commit()
    return cur.rowcount > 0


def seed_default_workflows() -> int:
    """
    Insert seed workflows on first launch (only if the workflows table is empty).
    Returns number of workflows created (0 if already seeded).
    """
    db = get_db()
    count = db.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]
    if count > 0:
        return 0
    for wf in _SEED_WORKFLOWS:
        create_workflow(WorkflowCreate(
            name=wf["name"],
            color=wf["color"],
            description=wf["description"],
        ))
    return len(_SEED_WORKFLOWS)


def _upsert_composition(db, parent_id: str, steps: list[WorkflowCompositionStepInput]) -> None:
    for step in steps:
        db.execute(
            """
            INSERT OR REPLACE INTO workflow_composition (parent_id, child_id, typical_pct, display_order)
            VALUES (?, ?, ?, ?)
            """,
            (parent_id, step.child_id, step.typical_pct, step.display_order),
        )


def _load_composition(wf_id: str) -> list[WorkflowCompositionStep]:
    db = get_db()
    rows = db.execute(
        """
        SELECT wc.child_id, w.name, w.color, wc.typical_pct, wc.display_order
        FROM workflow_composition wc
        JOIN workflows w ON wc.child_id = w.id
        WHERE wc.parent_id = ?
        ORDER BY wc.display_order, w.name
        """,
        (wf_id,),
    ).fetchall()
    return [
        WorkflowCompositionStep(
            child_id=r["child_id"],
            child_name=r["name"],
            child_color=r["color"],
            typical_pct=r["typical_pct"],
            display_order=r["display_order"],
        )
        for r in rows
    ]


def get_workflow_stats(
    wf_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> WorkflowStats | None:
    """
    Return time breakdown for a composite workflow by aggregating sessions
    whose context_workflow_id matches wf_id.
    """
    db = get_db()
    if db.execute("SELECT id FROM workflows WHERE id = ?", (wf_id,)).fetchone() is None:
        return None

    conditions = ["s.context_workflow_id = ?"]
    params: list = [wf_id]
    if start_date is not None:
        conditions.append("s.started_at >= ?")
        params.append(start_date.isoformat())
    if end_date is not None:
        conditions.append("s.started_at < ?")
        params.append((end_date + timedelta(days=1)).isoformat())
    where = " AND ".join(conditions)

    rows = db.execute(
        f"""
        SELECT w.id, w.name, w.color,
               SUM(s.duration) AS total_dur,
               COUNT(s.id) AS sess_count
        FROM sessions s
        JOIN workflows w ON s.workflow_id = w.id
        WHERE {where}
        GROUP BY s.workflow_id
        ORDER BY total_dur DESC
        """,
        params,
    ).fetchall()

    typical_rows = db.execute(
        "SELECT child_id, typical_pct FROM workflow_composition WHERE parent_id = ?",
        (wf_id,),
    ).fetchall()
    typical = {r["child_id"]: r["typical_pct"] for r in typical_rows}

    total_dur = sum(r["total_dur"] for r in rows) or 1.0
    breakdown = [
        WorkflowBreakdownItem(
            child_id=r["id"],
            child_name=r["name"],
            child_color=r["color"],
            actual_duration=r["total_dur"],
            actual_pct=round(r["total_dur"] / total_dur, 4),
            typical_pct=typical.get(r["id"]),
            session_count=r["sess_count"],
        )
        for r in rows
    ]
    return WorkflowStats(
        workflow_id=wf_id,
        total_duration=sum(r["total_dur"] for r in rows),
        session_count=sum(r["sess_count"] for r in rows),
        breakdown=breakdown,
    )


def _row_to_workflow(row) -> Workflow:
    is_composite = bool(row["is_composite"]) if "is_composite" in row.keys() else False
    composition = _load_composition(row["id"]) if is_composite else []
    return Workflow(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        color=row["color"],
        is_composite=is_composite,
        composition=composition,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        archived=bool(row["archived"]),
    )
