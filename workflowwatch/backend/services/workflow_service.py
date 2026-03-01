import uuid
from datetime import datetime, timezone

from ..database import get_db
from ..models import Workflow, WorkflowCreate, WorkflowUpdate

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
        INSERT INTO workflows (id, name, description, color, created_at, updated_at, archived)
        VALUES (?, ?, ?, ?, ?, ?, 0)
        """,
        (wf_id, body.name, body.description or None, color, now, now),
    )
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
    if not updates:
        return _row_to_workflow(row)
    updates.append("updated_at = ?")
    params.append(_now_iso())
    params.append(wf_id)
    db.execute(
        f"UPDATE workflows SET {', '.join(updates)} WHERE id = ?",
        params,
    )
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


def _row_to_workflow(row) -> Workflow:
    return Workflow(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        color=row["color"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        archived=bool(row["archived"]),
    )
