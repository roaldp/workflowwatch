from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TimelineEvent(BaseModel):
    aw_bucket_id: str
    aw_event_id: int
    timestamp: datetime
    duration: float
    data: dict[str, Any]
    session_id: str | None = None
    workflow_name: str | None = None
    workflow_color: str | None = None
    # WP-7: auto-label fields (populated when ?auto_label=true)
    suggested_workflow_id: str | None = None
    suggested_workflow_name: str | None = None
    suggested_workflow_color: str | None = None
    suggestion_confidence: str | None = None  # "high" | "medium"
    suggestion_source: str | None = None      # "cache" | "embedding"
    suggestion_explanation: str | None = None


class BucketInfo(BaseModel):
    window: str | None = None
    afk: str | None = None
    browser: list[str] = []


class HealthResponse(BaseModel):
    status: str
    aw_connected: bool
    aw_server_url: str
    buckets: BucketInfo
    db_path: str


class WorkflowCreate(BaseModel):
    name: str
    description: str | None = None
    color: str | None = None  # hex, e.g. "#3B82F6"


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None


class Workflow(BaseModel):
    id: str
    name: str
    description: str | None
    color: str | None
    created_at: str
    updated_at: str
    archived: bool


class SessionEventRef(BaseModel):
    aw_bucket_id: str
    aw_event_id: int


class SessionCreate(BaseModel):
    workflow_id: str
    date: str  # YYYY-MM-DD, timeline date for resolving event refs
    title: str | None = None
    notes: str | None = None
    events: list[SessionEventRef]  # at least one


class Session(BaseModel):
    id: str
    workflow_id: str
    title: str | None
    started_at: str
    ended_at: str
    duration: float
    notes: str | None
    created_at: str
    updated_at: str


class SessionUpdate(BaseModel):
    title: str | None = None
    notes: str | None = None


class SessionEventSnapshot(BaseModel):
    aw_bucket_id: str
    aw_event_id: int
    event_timestamp: str
    event_duration: float
    event_data: dict[str, Any] | None = None


class SessionWithEvents(Session):
    events: list[SessionEventSnapshot] = []


class SessionEventsBody(BaseModel):
    events: list[SessionEventRef]


# WP-7: Auto-label accept / dismiss request models

class AutoLabelAcceptItem(BaseModel):
    aw_bucket_id: str
    aw_event_id: int
    workflow_id: str


class AutoLabelAcceptBody(BaseModel):
    date: str  # YYYY-MM-DD
    accepts: list[AutoLabelAcceptItem]


class AutoLabelDismissItem(BaseModel):
    aw_bucket_id: str
    aw_event_id: int
    workflow_id: str
    signature: str | None = None  # pre-computed by client if available


class AutoLabelDismissBody(BaseModel):
    date: str  # YYYY-MM-DD
    dismissals: list[AutoLabelDismissItem]


class AutoLabelStats(BaseModel):
    cache_entries: int
    workflows_covered: int
    dismissals: int
    embedding_available: bool


# Label rules (Tier 0)

class LabelRuleCreate(BaseModel):
    workflow_id: str
    rule_type: str   # "app" | "title_keyword"
    match_value: str


class LabelRule(BaseModel):
    id: str
    workflow_id: str
    rule_type: str
    match_value: str
    created_at: str
    workflow_name: str
    workflow_color: str | None
