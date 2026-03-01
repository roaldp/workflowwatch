# WP-4: Event Labeling (Core Feature)

> **Goal:** Let the user select events on the timeline (or in the event list) and label them as a workflow. Labeling creates a session; the timeline and event list update to show labeled events with the workflow's color.
>
> **Testable outcome:** Select one or more events, choose "Label as…" → pick a workflow → events are assigned to a new session; timeline and list show workflow color/badge. Refreshing the date keeps the labels.

---

## Prerequisites

- WP-1, WP-2, WP-3 complete (backend with timeline and session annotation; frontend with workflows sidebar and timeline view).
- Backend already has `sessions` and `session_events` tables; timeline endpoint returns `session_id`, `workflow_name`, `workflow_color` for labeled events.

---

## Deliverables

| # | Deliverable | Requirement refs |
|---|-------------|------------------|
| 1 | Backend: POST /api/v1/sessions (create session with event refs) | B-SE-1, B-SE-2 |
| 2 | Backend: session service fetches events from AW, snapshots data, computes started_at/ended_at/duration | B-SE-2 |
| 3 | Frontend: select events (checkboxes in event list; optional: click blocks on timeline) | F-TL-4 |
| 4 | Frontend: "Label as…" action with workflow dropdown (active workflows only) | F-TL-6, F-WF-4 |
| 5 | Labeling creates session → refetch timeline; labeled events show workflow color/badge | F-TL-7 |
| 6 | (Optional) Unlabel: remove events from session; delete session if no events left | F-TL-8 |

---

## Tasks

### 1. Backend: Session models and service

**Pydantic models** (add to `backend/models.py`):

```python
class SessionEventRef(BaseModel):
    aw_bucket_id: str
    aw_event_id: int

class SessionCreate(BaseModel):
    workflow_id: str
    title: str | None = None
    notes: str | None = None
    events: list[SessionEventRef]   # at least one

class Session(BaseModel):
    id: str
    workflow_id: str
    title: str | None
    started_at: str   # ISO 8601
    ended_at: str
    duration: float   # seconds
    notes: str | None
    created_at: str
    updated_at: str
```

**Service** `backend/services/session_service.py`:

- `create_session(body: SessionCreate, aw_service, get_timeline_events_for_range) -> Session`
  - Validate `workflow_id` exists and is not archived.
  - For each event ref, ensure it is not already in `session_events` (one event → at most one session). If any are already labeled, return 409 or skip those and document.
  - Fetch event data from AW for each ref (same buckets as timeline; get event by bucket_id + event_id or by time range and match).
  - Insert `sessions` row: id (UUID), workflow_id, title, notes, started_at = min(event timestamps), ended_at = max(event end), duration = sum(event durations), created_at/updated_at.
  - Insert `session_events` rows: for each event, snapshot `event_data` (JSON), event_timestamp, event_duration.
  - Return Session.
- Optional for WP-4: `remove_events_from_session(session_id, event_refs) -> Session | None`; if no events left, delete session.

**Router** `backend/routers/sessions.py`:

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/api/v1/sessions` | `SessionCreate` (workflow_id, title?, notes?, events: [{aw_bucket_id, aw_event_id}])` | `Session` (201) or 400/404/409 |

Error cases:
- 404: workflow_id not found or archived.
- 400: events list empty, or invalid event refs.
- 409: one or more events already belong to a session (v1: one event, one session).

Register the router in `main.py`.

**Fetching event data from AW:** For each `(aw_bucket_id, aw_event_id)` you need the event's timestamp, duration, and data. Options:
- (A) Fetch events for the day from AW (reuse timeline merge logic), then filter to the requested refs. Requires date; frontend can send the timeline date or you derive from first event ref after fetching.
- (B) Query AW bucket events in a time window (e.g. event_id ± small window) and find the event by id. AW API typically allows `GET /api/0/buckets/{id}/events?start=&end=`; then find event with matching id in the list.

Recommendation: Reuse timeline service. Given a list of event refs, get the current timeline for a date that covers those events (e.g. from first ref’s timestamp). Timeline already returns merged, AFK-filtered events. Match each ref to a timeline event by `aw_bucket_id` + `aw_event_id`; use that event’s timestamp, duration, data for the snapshot. If a ref doesn’t appear in the timeline (e.g. AFK-filtered, or wrong date), reject that ref with 400.

### 2. Frontend: Event selection

- **Event list:** Add a checkbox column (or row checkbox). Maintain a set of selected event keys: `{aw_bucket_id}:{aw_event_id}`.
- **Selection state:** In timeline store or a small composable: `selectedEventIds: Set<string>`, `toggleEvent(event)`, `clearSelection()`, `selectAll()`. Only allow selecting events that are not already labeled (`session_id == null`); disable or hide checkbox for labeled events (or allow selection for unlabel flow in a later task).
- **Timeline bar (optional for WP-4):** Clicking a block toggles selection; selected blocks get a distinct style (e.g. ring or opacity). If time is short, WP-4 can ship with list-only selection.

### 3. Frontend: "Label as…" action

- When at least one event is selected, show a **"Label as…"** button or bar (e.g. above the event list or floating).
- Clicking it opens a **dropdown** (or modal) listing **active workflows** (same source as sidebar: GET /api/v1/workflows, exclude archived). Show workflow name and color dot.
- On picking a workflow:
  - Call `POST /api/v1/sessions` with `{ workflow_id, events: [{ aw_bucket_id, aw_event_id } for each selected] }`.
  - On success: clear selection, call timeline store’s `fetchTimeline()` so the timeline and list refresh; newly labeled events now show `workflow_name` and `workflow_color`.
  - On error: show message (e.g. "One or more events are already labeled" or "Workflow not found").

### 4. API client and types

- **Types:** `Session`, `SessionCreate`, `SessionEventRef` in frontend (e.g. `src/types/session.ts` or in api layer).
- **Client:** `api.post('/api/v1/sessions', body)`.

### 5. Unlabel (optional for WP-4)

- Backend: `DELETE /api/v1/sessions/{id}/events` with body `{ events: [SessionEventRef] }`. Remove those event rows from `session_events`; recompute session’s started_at, ended_at, duration; if no events left, delete the session. Return updated Session or 204.
- Frontend: For events that have `session_id`, show an "Unlabel" or "Remove from workflow" action (e.g. in a context menu or in the event list row). On confirm, call delete-events API, then refetch timeline.

If scope is tight, defer unlabel to WP-5 (Session management).

---

## Technical notes

- **One event, one session:** Enforce in backend: before inserting session_events, check that no (aw_bucket_id, aw_event_id) already exists in `session_events`. If any do, return 409 and list which events are already labeled.
- **Date for timeline fetch:** When creating a session, the frontend knows the current timeline date. Backend can derive the date from the first event’s timestamp when fetching from AW, or the frontend can send `date` in the request body (optional) so the backend knows which day’s timeline to use for resolving event refs.
- **Archived workflows:** Excluded from "Label as…" dropdown (F-WF-4). Use existing workflow list that filters `archived=false`.

---

## Testing Plan

| # | Test | How to verify |
|---|------|---------------|
| 1 | Create session with one event | Select one event, Label as "Startup Sourcing" → session created, timeline shows that event with workflow color |
| 2 | Create session with multiple events | Select several consecutive events, label → one session; all show same workflow badge |
| 3 | Refetch preserves labels | After labeling, change date and back, or reload page → labeled events still show workflow |
| 4 | Cannot label already-labeled event | Select an event that’s already in a session, try Label as → error or dropdown disabled for that event |
| 5 | Archived workflow not in dropdown | Archive a workflow → it does not appear in "Label as…" list |
| 6 | Empty selection hides "Label as…" | Deselect all → "Label as…" button hidden or disabled |
| 7 | Backend rejects duplicate event ref | POST session with an event that’s already in another session → 409 |

---

## Definition of Done

- [ ] Backend: POST /api/v1/sessions creates a session, snapshots event data from AW, computes times, inserts session_events; returns Session.
- [ ] Backend: Rejects event refs that are already in a session (409 or 400).
- [ ] Frontend: User can select one or more unlabeled events (event list checkboxes; timeline blocks optional).
- [ ] Frontend: "Label as…" shows active workflows; choosing one creates session and refetches timeline.
- [ ] Labeled events display with workflow color on timeline and workflow badge in event list.
- [ ] (Optional) Unlabel / remove events from session implemented and tested.
- [ ] All tests in the testing plan pass.
