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


class WorkflowCompositionStepInput(BaseModel):
    child_id: str
    typical_pct: float | None = None  # 0.0–1.0, advisory
    display_order: int = 0


class WorkflowCompositionStep(BaseModel):
    child_id: str
    child_name: str
    child_color: str | None
    typical_pct: float | None
    display_order: int


class WorkflowCreate(BaseModel):
    name: str
    description: str | None = None
    color: str | None = None  # hex, e.g. "#3B82F6"
    is_composite: bool = False
    composition: list[WorkflowCompositionStepInput] = []


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None
    composition: list[WorkflowCompositionStepInput] | None = None  # None = no change, [] = clear


class Workflow(BaseModel):
    id: str
    name: str
    description: str | None
    color: str | None
    is_composite: bool
    composition: list[WorkflowCompositionStep] = []  # populated for composite workflows
    created_at: str
    updated_at: str
    archived: bool


class WorkflowBreakdownItem(BaseModel):
    child_id: str
    child_name: str
    child_color: str | None
    actual_duration: float   # seconds
    actual_pct: float        # 0.0–1.0
    typical_pct: float | None
    session_count: int


class WorkflowStats(BaseModel):
    workflow_id: str
    total_duration: float
    session_count: int
    breakdown: list[WorkflowBreakdownItem]


class SessionEventRef(BaseModel):
    aw_bucket_id: str
    aw_event_id: int


class SessionCreate(BaseModel):
    workflow_id: str
    date: str  # YYYY-MM-DD, timeline date for resolving event refs
    title: str | None = None
    notes: str | None = None
    events: list[SessionEventRef]  # at least one
    context_workflow_id: str | None = None  # optional composite process this session belongs to


class Session(BaseModel):
    id: str
    workflow_id: str
    context_workflow_id: str | None = None  # composite process, if assigned
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
    context_workflow_id: str | None = None  # pass empty string "" to clear


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


# Daily Streak & Swipe Card models

class StreakData(BaseModel):
    date: str
    total_xp: int
    today_xp: int
    current_streak: int


class SwipeCardItem(BaseModel):
    aw_bucket_id: str
    aw_event_id: int
    timestamp: datetime
    duration: float
    data: dict[str, Any]
    suggested_workflow_id: str
    suggested_workflow_name: str | None = None
    suggested_workflow_color: str | None = None
    suggestion_confidence: str  # "high" | "medium"
    suggestion_source: str      # "cache" | "embedding" | "rule"


class SwipeCardQueue(BaseModel):
    date: str
    cards: list[SwipeCardItem]
    total_unlabeled: int
    total_with_suggestions: int


class SwipeActionBody(BaseModel):
    date: str
    aw_bucket_id: str
    aw_event_id: int
    workflow_id: str
