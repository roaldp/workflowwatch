# WP-5: Session Management

> **Goal:** Let the user review past sessions, see their linked events, and edit or delete sessions. Support unlabeling (removing events from a session); if all events are removed, the session is deleted.
>
> **Testable outcome:** Open a sessions view, see sessions grouped by day; expand a session to see its events; edit title/notes, delete a session, or remove specific events from a session (timeline updates). Filter sessions by workflow.

---

## Prerequisites

- WP-1 through WP-4 complete (backend with POST /sessions; frontend with timeline, event list, and "Label as…").
- Backend has `sessions` and `session_events` tables; session creation and timeline annotation already work.

---

## Deliverables

| # | Deliverable | Requirement refs |
|---|-------------|------------------|
| 1 | Backend: GET /api/v1/sessions (list with workflow_id, start, end, limit, offset) | B-SE-5 |
| 2 | Backend: GET /api/v1/sessions/:id (session with linked events and snapshot data) | B-SE-6 |
| 3 | Backend: PUT /api/v1/sessions/:id (title, notes) | B-SE-3 |
| 4 | Backend: DELETE /api/v1/sessions/:id (hard delete) | B-SE-4 |
| 5 | Backend: POST /api/v1/sessions/:id/events (add events), DELETE (remove events); recompute session times; delete session if no events left | B-SE-3, F-TL-8 |
| 6 | Frontend: Sessions view — list sessions for date range, grouped by day | F-SE-1 |
| 7 | Frontend: Session cards with workflow name (color), title, start–end, duration, event count; expand to show events | F-SE-2, F-SE-3 |
| 8 | Frontend: Edit session (title, notes), delete session | F-SE-4 |
| 9 | Frontend: Unlabel — remove events from session (from timeline/event list or from session detail); refetch timeline/sessions | F-TL-8 |
| 10 | Frontend: Filter sessions by workflow (optional: dropdown or tabs) | F-SE-5 |

---

## Tasks

### 1. Backend: Session list and get-one

**Models** (add to `backend/models.py` if not present):

- Reuse `Session`. For GET one with events, add a response model that includes events, e.g.:

```python
class SessionEventSnapshot(BaseModel):
    aw_bucket_id: str
    aw_event_id: int
    event_timestamp: str   # ISO
    event_duration: float
    event_data: dict | None  # snapshot (app, title, url, etc.)

class SessionWithEvents(Session):
    events: list[SessionEventSnapshot] = []
```

**Service** `backend/services/session_service.py`:

- `list_sessions(workflow_id: str | None, start: date | None, end: date | None, limit: int, offset: int) -> list[Session]`
  - Query `sessions` with optional filter by `workflow_id`, and by `started_at` in [start, end] if start/end given.
  - Order by `started_at` desc. Apply limit/offset. Return list of Session (no events).
- `get_session(session_id: str) -> SessionWithEvents | None`
  - Fetch session row; if not found return None.
  - Fetch all `session_events` for this session; for each, parse `event_data` JSON and build `SessionEventSnapshot`.
  - Return SessionWithEvents.

**Router** `backend/routers/sessions.py`:

| Method | Path | Query / Body | Response |
|--------|------|--------------|----------|
| GET | `/api/v1/sessions` | `workflow_id?`, `start?` (YYYY-MM-DD), `end?`, `limit?`, `offset?` | `Session[]` |
| GET | `/api/v1/sessions/{id}` | — | `SessionWithEvents` or 404 |

---

### 2. Backend: Update and delete session

**Service:**

- `update_session(session_id: str, title: str | None, notes: str | None) -> Session | None`
  - Update only provided fields; set `updated_at`. Return updated Session or None.
- `delete_session(session_id: str) -> bool`
  - DELETE from sessions (session_events cascade). Return True if a row was deleted.

**Router:**

| Method | Path | Body | Response |
|--------|------|------|----------|
| PUT | `/api/v1/sessions/{id}` | `{title?, notes?}` | `Session` or 404 |
| DELETE | `/api/v1/sessions/{id}` | — | 204 or 404 |

---

### 3. Backend: Add / remove events from session

**Service:**

- `add_events_to_session(session_id: str, event_refs: list[SessionEventRef], aw) -> Session | None`
  - Validate session exists. For each ref: check not already in any session_events (including this session); fetch event from timeline for the session’s date range (derive date from session.started_at); insert session_event row with snapshot. Recompute session.started_at, ended_at, duration from all session_events; update session row. Return updated Session or None.
- `remove_events_from_session(session_id: str, event_refs: list[SessionEventRef]) -> Session | None`
  - Delete matching session_events rows. Recompute session times from remaining events; if no events left, delete the session and return None (or return 204 for “session deleted”). If events remain, update session row and return updated Session.

Recompute logic: `started_at = min(event_timestamp)`, `ended_at = max(event_timestamp + event_duration)`, `duration = sum(event_duration)`.

**Router:**

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/api/v1/sessions/{id}/events` | `{events: [SessionEventRef]}` | `Session` or 400/404/409 |
| DELETE | `/api/v1/sessions/{id}/events` | `{events: [SessionEventRef]}` | `Session` (updated), or 204 if session deleted, or 404 |

---

### 4. Frontend: Sessions view and navigation

- **Placement:** Add a way to open the Sessions view (e.g. a “Sessions” link or tab in the header/sidebar next to the timeline). Main content can switch between Timeline view and Sessions view (simple toggle or tab; routing optional).
- **Sessions store** (`stores/sessions.ts`): state `sessions: Session[]`, `loading`, `error`; params `start`, `end`, `workflowId` (optional). Actions: `fetchSessions(start, end, workflowId?)`, `fetchSession(id)` for detail. Call GET /sessions and GET /sessions/:id.
- **Date range:** Reuse timeline date for “today” or add a range selector (e.g. “This week”, “This month”, or start/end date inputs). For v1, “sessions for the selected timeline date” or “sessions for the last 7 days” is enough; optional: full range picker in WP-6.

---

### 5. Frontend: Session list and cards

- **SessionsView.vue:** Fetch sessions for the chosen range; group by day (group by date of `started_at`). Render a section per day with a list of session cards.
- **SessionCard.vue:** Shows workflow name (with color dot), optional title, start–end time (formatted), total duration, event count. Click to expand (or “Expand” button). When expanded, show list of linked events (from GET /sessions/:id or from list response if backend returns event count only — for expand, fetch GET /sessions/:id to get event details). Event row: app, title, URL (if any), duration.
- **Edit / Delete:** On the card (or in expanded view): “Edit” opens a small form/modal for title and notes; “Delete” with confirm, then DELETE /sessions/:id and remove from list / refetch.
- **Filter by workflow:** Dropdown or tabs to set `workflowId` and refetch sessions (optional for first slice).

---

### 6. Frontend: Unlabel (remove events from session)

- **From timeline/event list:** For events that have `session_id`, show “Remove from workflow” or “Unlabel”. On confirm: call DELETE /api/v1/sessions/:id/events with body `{ events: [{ aw_bucket_id, aw_event_id }] }` for that event (and session_id from the event). Then refetch timeline (and sessions list if visible).
- **From session detail:** In the expanded event list, “Remove” per event; same API, then refetch session (or refetch sessions list) and timeline so the timeline bar updates.

---

## Technical notes

- **Session list date range:** Backend filters by `started_at >= start` and `started_at < end+1` (or similar). Use ISO date strings; backend parses to date.
- **Recompute on add/remove:** Same formula as in create_session: started_at, ended_at, duration from current set of session_events. Run in a transaction.
- **Unlabel and timeline:** After removing an event from a session, the timeline for that day should show the event as unlabeled (session_id null). Timeline service already reads from session_events, so deleting the session_event row is enough; next timeline fetch will show it unlabeled.

---

## Testing Plan

| # | Test | How to verify |
|---|------|---------------|
| 1 | List sessions | GET /sessions?start=2026-02-01&end=2026-02-28 → list of sessions, newest first |
| 2 | List filtered by workflow | GET /sessions?workflow_id=... → only that workflow’s sessions |
| 3 | Get session with events | GET /sessions/:id → session + events array with event_data |
| 4 | Update session title/notes | PUT /sessions/:id → session updated; GET shows new values |
| 5 | Delete session | DELETE /sessions/:id → 204; GET timeline shows those events unlabeled |
| 6 | Remove one event from session | DELETE /sessions/:id/events with one ref → session duration updated; that event unlabeled on timeline |
| 7 | Remove all events | DELETE last events → session deleted; timeline shows all unlabeled |
| 8 | Add events to session | POST /sessions/:id/events → session duration/range updated |
| 9 | Sessions view shows cards | Open Sessions, see sessions grouped by day; expand card → events list |
| 10 | Unlabel from timeline | On labeled event, Unlabel → event loses workflow badge; session updated or deleted |

---

## Definition of Done

- [ ] Backend: GET list, GET one (with events), PUT, DELETE, POST/DELETE events implemented and documented.
- [ ] Frontend: Sessions view with list grouped by day; session cards with expand and event list; edit title/notes and delete session.
- [ ] Frontend: Unlabel from timeline/event list and/or from session detail; timeline and sessions list stay in sync.
- [ ] Optional: filter sessions by workflow.
- [ ] All tests in the testing plan pass.
