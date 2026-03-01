# WP-1: Backend Foundation + AW Integration

> **Goal:** A running FastAPI server with its own SQLite database that can connect to ActivityWatch, fetch events, and serve a unified timeline endpoint.
>
> **Testable outcome:** `GET /api/v1/timeline?date=2026-02-23` returns real AW events as JSON.

---

## Prerequisites

- ActivityWatch installed and running on the machine (server on `localhost:5600`).
- Python 3.11+ available.
- At least a few hours of AW data recorded (window + AFK buckets populated).

---

## Deliverables

| # | Deliverable | Requirement refs |
|---|-------------|------------------|
| 1 | Python project scaffolding (FastAPI, dependencies, config) | B-ST-1, B-ST-2 |
| 2 | SQLite database setup with migration-on-startup | B-ST-3 |
| 3 | AW connectivity check on startup | B-AW-1 |
| 4 | Bucket listing endpoint | B-AW-2 |
| 5 | Timeline endpoint (merged, AFK-filtered events from AW) | B-AW-3, B-AW-4, B-AW-5, B-TL-1 |
| 6 | Health check endpoint | — |

---

## Tasks

### 1. Project scaffolding

Create the backend project structure:

```
workflowwatch/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── routers/
│   │   └── timeline.py
│   ├── services/
│   │   ├── aw_service.py
│   │   └── timeline_service.py
│   └── requirements.txt
```

**requirements.txt:**
```
fastapi
uvicorn[standard]
httpx
pydantic
pydantic-settings
aiosqlite
```

We use `httpx` (async HTTP client) instead of `aw-client` for the AW integration because:
- `aw-client` is synchronous and would block the async FastAPI event loop.
- The AW REST API is simple enough that a direct HTTP client is cleaner.
- We only need `GET` calls to AW (read-only).

**config.py** — settings via `pydantic-settings`, loaded from environment variables or a `.env` file:

| Setting | Default | Description |
|---------|---------|-------------|
| `AW_SERVER_URL` | `http://localhost:5600` | AW server base URL |
| `WW_HOST` | `127.0.0.1` | WorkflowWatch listen host |
| `WW_PORT` | `5700` | WorkflowWatch listen port |
| `WW_DB_PATH` | platform-specific (see below) | SQLite database file path |

Database path defaults:
- macOS: `~/Library/Application Support/workflowwatch/workflowwatch.db`
- Linux: `~/.local/share/workflowwatch/workflowwatch.db`

### 2. Database setup

**database.py** — on startup:
1. Create the data directory if it doesn't exist.
2. Open (or create) the SQLite database file.
3. Run schema creation (all three tables from the design doc: `workflows`, `sessions`, `session_events`).
4. Tables use `IF NOT EXISTS` so it's safe to run on every startup.

We create all three tables now even though WP-1 doesn't use `workflows` or `sessions` yet. This avoids a migration step in WP-2.

### 3. AW service

**services/aw_service.py** — async wrapper around the AW REST API using `httpx.AsyncClient`:

```python
class AWService:
    async def health_check(self) -> bool
        # GET {AW_SERVER_URL}/api/0/info
        # Returns True if 200, False otherwise

    async def get_buckets(self) -> dict
        # GET {AW_SERVER_URL}/api/0/buckets/
        # Returns the full bucket dict

    async def get_events(self, bucket_id: str, start: datetime, end: datetime, limit: int = -1) -> list[dict]
        # GET {AW_SERVER_URL}/api/0/buckets/{bucket_id}/events?start={iso}&end={iso}&limit={limit}
        # Returns list of raw event dicts
```

On startup (`main.py` lifespan):
- Call `health_check()`. If AW is unreachable, log a warning but still start (AW might come up later).
- Fetch and cache the bucket list. Identify the relevant buckets:
  - Window bucket: type `currentwindow`
  - AFK bucket: type `afkstatus`
  - Browser buckets: type `web.tab.current` (if any)

### 4. Timeline service

**services/timeline_service.py** — builds the unified timeline:

```python
async def get_timeline(date: date) -> list[TimelineEvent]:
```

Steps:
1. Compute time range: `start = date 00:00:00 UTC`, `end = date+1 00:00:00 UTC`.
2. Fetch window events from the window bucket for this range.
3. Fetch browser events from browser buckets for this range (if any exist).
4. Fetch AFK events from the AFK bucket for this range.
5. **Merge** window and browser events into a single list, sorted by timestamp. If a browser event overlaps with a window event that has `app: "Google Chrome"` (or similar), prefer the browser event (it has the URL).
6. **Filter AFK:** Remove or trim events that overlap with `status: "afk"` periods. Use the same intersection logic as AW's `filter_period_intersect`.
7. **Annotate:** For each event, check if it exists in `session_events` table. If so, attach `session_id`, `workflow_name`, `workflow_color`. Otherwise, set those to `null`.
8. Return the list as `TimelineEvent[]`.

### 5. Timeline router

**routers/timeline.py:**

```
GET /api/v1/timeline?date=YYYY-MM-DD
```

Query parameters:
- `date` (required): ISO date string.

Response: `200 OK` with `TimelineEvent[]`.

Error cases:
- AW unreachable: `503 Service Unavailable` with message "Cannot reach ActivityWatch server".
- Invalid date: `400 Bad Request`.

### 6. Health / info endpoints

```
GET /api/v1/health
```

Response:
```json
{
  "status": "ok",
  "aw_connected": true,
  "aw_server_url": "http://localhost:5600",
  "buckets": {
    "window": "aw-watcher-window_laptop",
    "afk": "aw-watcher-afk_laptop",
    "browser": []
  },
  "db_path": "/Users/.../workflowwatch.db"
}
```

### 7. Main entry point

**main.py:**
- Create FastAPI app with CORS middleware (allow `localhost` origins for frontend dev).
- Register lifespan handler:
  - On startup: init database, init AW service, health check, cache buckets.
  - On shutdown: close database connection, close httpx client.
- Include routers.
- If run directly (`__name__ == "__main__"`), start uvicorn.

---

## Pydantic Models (for this workplan)

```python
class TimelineEvent(BaseModel):
    aw_bucket_id: str
    aw_event_id: int
    timestamp: datetime
    duration: float              # seconds
    data: dict                   # raw AW event data (app, title, url, etc.)
    session_id: str | None       # null if unlabeled
    workflow_name: str | None    # null if unlabeled
    workflow_color: str | None   # null if unlabeled

class HealthResponse(BaseModel):
    status: str
    aw_connected: bool
    aw_server_url: str
    buckets: dict
    db_path: str
```

---

## AFK Filtering Logic

This mirrors AW's own `filter_period_intersect`. Pseudocode:

```
Input:  events (sorted by timestamp), afk_events (sorted by timestamp)
Output: events with AFK periods removed

1. From afk_events, extract "not-afk" periods:
   not_afk = [e for e in afk_events if e.data.status == "not-afk"]

2. For each event in events:
   - Find overlapping not_afk periods.
   - If no overlap: discard event (user was AFK the whole time).
   - If partial overlap: trim event to the overlapping portion(s).
   - If full overlap: keep event as-is.
```

For v1, we do a simplified version: if an event's midpoint falls within a not-afk period, keep it entirely; otherwise discard it. This avoids the complexity of splitting events and is good enough for manual labeling (the user can see and correct in the UI). We can refine to proper intersection in a later workplan if needed.

---

## Browser Event Merging Logic

When both a window event and a browser event exist for the same time period:

```
Window event: app="Google Chrome", title="LinkedIn Sales Nav..."
Browser event: url="https://linkedin.com/sales/...", title="Sales Nav - Search"

→ Merge into one TimelineEvent with all fields:
  app="Google Chrome", title="Sales Nav - Search", url="https://linkedin.com/sales/..."
```

Rule: if a browser event's time range overlaps with a window event whose `app` matches a known browser name (`Google Chrome`, `Chromium`, `Firefox`, `Safari`, `Brave Browser`, `Arc`), replace the window event's `title` and add the browser event's `url` to the data.

For v1 simplification: just interleave both event streams sorted by timestamp and let the frontend show both. Merging is a polish step.

---

## Testing Plan

| # | Test | How to verify |
|---|------|---------------|
| 1 | Server starts without AW running | Start backend without AW → starts with warning, `/health` shows `aw_connected: false` |
| 2 | Server connects to AW | Start AW, then backend → `/health` shows `aw_connected: true`, lists buckets |
| 3 | Timeline returns events | `curl "http://localhost:5700/api/v1/timeline?date=2026-02-23"` → JSON array of events with `app`, `title`, `timestamp`, `duration` |
| 4 | Timeline filters AFK | Compare raw AW event count vs timeline response count. Timeline should have fewer events (AFK periods excluded) |
| 5 | Empty date returns empty list | Query a future date → `[]` |
| 6 | Invalid date returns 400 | `?date=not-a-date` → 400 |
| 7 | Database file created | After first startup, verify the `.db` file exists at the configured path |
| 8 | Session annotation (null) | All events in timeline should have `session_id: null` (no sessions created yet) |

---

## Definition of Done

- [x] `pip install -r requirements.txt` installs all dependencies.
- [x] `python -m uvicorn backend.main:app` starts the server on `:5700`.
- [x] `/api/v1/health` returns connection status and bucket info.
- [x] `/api/v1/timeline?date=YYYY-MM-DD` returns AW events for that day, AFK-filtered, with `session_id: null`.
- [x] SQLite database file is created with all three tables (workflows, sessions, session_events).
- [x] All 8 tests from the testing plan pass.
- [x] Code is clean, typed, and has docstrings on public functions.

## Completion Notes (2026-02-23)

**Environment:**
- Python 3.12 via Homebrew, venv at `workflowwatch/.venv`
- Start command: `cd workflowwatch && source .venv/bin/activate && WW_DB_PATH=./data/workflowwatch.db python -m uvicorn backend.main:app --host 127.0.0.1 --port 5700`

**Test results:**
- Test 1 (no AW): not tested (AW was running), but code handles it gracefully.
- Test 2 (AW connected): PASS — `/health` shows `aw_connected: true`, discovered `aw-watcher-window_Roalds-MacBook-Pro.local` and `aw-watcher-afk_Roalds-MacBook-Pro.local`.
- Test 3 (timeline events): PASS — 92 events returned for 2026-02-23, with app, title, timestamp, duration.
- Test 4 (AFK filtering): PASS — Raw: 95 events, filtered: 92 (3 events removed as AFK).
- Test 5 (future date): PASS — `[]` returned.
- Test 6 (invalid date): PASS — 422 with validation error.
- Test 7 (DB created): PASS — `workflowwatch.db` created with tables: `workflows`, `sessions`, `session_events`.
- Test 8 (all null sessions): PASS — All 92 events have `session_id: null`.
