# WP-3: Timeline Visualization

> **Goal:** Show today's (or any day's) AW events as a horizontal timeline of colored blocks and a scrollable event list. Add date navigation so the user can change the displayed day.
>
> **Testable outcome:** Open the app, pick a date (or use Today). See that day's AW events as colored blocks on a timeline and as a table/list with app, title, URL, start time, duration. Changing the date reloads the timeline.

---

## Prerequisites

- WP-1 and WP-2 complete (backend with `/api/v1/timeline?date=` and `/api/v1/workflows`; frontend shell with sidebar and workflow list).
- Backend returns `TimelineEvent[]` with `timestamp`, `duration`, `data` (app, title, url), and `session_id` / `workflow_name` / `workflow_color` for labeled events.

---

## Deliverables

| # | Deliverable | Requirement refs |
|---|-------------|------------------|
| 1 | Timeline view as the main content for the shell | F-TL-1, F-TL-3 |
| 2 | Horizontal timeline bar: one block per event, colored by app (or workflow if labeled) | F-TL-1, F-TL-2 |
| 3 | Event list below timeline: app, title, URL, start time, duration; scrollable | F-TL-3 |
| 4 | Date navigation: prev/next day, date picker, "Today" | F-TL-9 |
| 5 | Fetch timeline from API for selected date; loading and error states | — |
| 6 | (Optional) Visually distinguish labeled events on timeline (e.g. workflow color border) | F-TL-2 |

---

## Tasks

### 1. Timeline API integration

- **Store or composable:** Add a way to fetch timeline for a given date. Options:
  - New Pinia store `timeline` with state: `events: TimelineEvent[]`, `date: string` (YYYY-MM-DD), `loading`, `error`. Actions: `fetchTimeline(date: string)`.
  - Or a composable `useTimeline(date)` that returns `{ events, loading, error, refetch }` and calls the API.
- **API:** `GET /api/v1/timeline?date=YYYY-MM-DD` (already exists). Frontend type `TimelineEvent` should match backend: `aw_bucket_id`, `aw_event_id`, `timestamp`, `duration`, `data`, `session_id`, `workflow_name`, `workflow_color`.
- **Date:** Store selected date in the timeline store or in a shared "view state" (e.g. in the shell). Default to today (local date as YYYY-MM-DD).

### 2. Date navigation (header)

- Add to the shell header (or to the timeline view):
  - **"Today"** button: sets date to today and refetches.
  - **Prev day (◀)** and **Next day (▶):** decrement/increment the selected date by one day, then refetch.
  - **Date picker:** An input `type="date"` or a dropdown that shows the current date and allows picking a day. On change, refetch timeline for that date.
- Ensure the selected date is used when calling the timeline API (e.g. when the timeline view mounts or when the date changes).

### 3. Timeline bar component

- **Input:** List of `TimelineEvent[]` and the selected date’s time range (start of day 00:00 to end of day 23:59:59) for mapping to pixel positions.
- **Layout:** A horizontal bar representing the full day (e.g. 24 hours or "earliest event to latest event" for that day). Each event is a block:
  - **Position:** Based on `event.timestamp` (and time range). Width based on `event.duration` (seconds).
  - **Color:** If `event.workflow_color` is set, use it (labeled event). Otherwise derive a color from `event.data.app` (e.g. hash app name to a hue, or use a small palette keyed by app).
- **Tooltip or label:** On hover (or click), show app name, window title, duration. Optional: show time range (e.g. "10:05 – 10:12").
- **Labeled events (F-TL-2):** Give events with `session_id` a distinct style: e.g. left border or outline in `workflow_color`, or a small workflow-name badge. So the user can see which blocks are already labeled.
- **Scaling:** If the day has no events or a very long gap, decide whether the bar is fixed to 24h or scales to "first event → last event". Recommendation: fixed 24h (00:00–24:00) so empty hours are visible; if no events at all, show an empty bar or a message.

### 4. Event list component

- **Input:** Same `TimelineEvent[]` (or take from store), sorted by `timestamp`.
- **Display:** Table or card list. Columns (or fields): **App**, **Title** (window title), **URL** (if present in `data.url`), **Start time** (format `event.timestamp` as time, e.g. HH:mm), **Duration** (e.g. "5m 30s" or "1h 2m").
- **Labeled:** If `workflow_name` is set, show a small badge or pill with workflow name (and optionally color). Keeps list and timeline consistent.
- **Scrollable:** If many events, make the list scrollable (e.g. `max-height` + `overflow-auto`). Timeline bar can stay fixed height; list below scrolls.

### 5. Wire into shell

- Replace the main content placeholder in `ShellView` with the timeline view:
  - Either a single **TimelineView** that contains: date navigation, timeline bar, event list.
  - Or: date navigation in the header (design §6.1 "[Today ▼] [◀ ▶]") and the main area = timeline bar + event list.
- On mount of the timeline view (or when the route is "timeline" if you add routing later), set the selected date to today and call `fetchTimeline(today)`.
- When the user changes the date (Today, prev, next, or date picker), update the selected date and call `fetchTimeline(newDate)`.

### 6. Empty and error states

- **No events for date:** Show a message like "No activity recorded for this day" (and still show the date nav and an empty timeline bar if desired).
- **API error:** Show an error message (e.g. "Could not load timeline" + retry button or show `error` from store).
- **Loading:** Show a loading indicator (skeleton or spinner) while `loading` is true.

### 7. AFK and gaps (optional for WP-3)

- Design F-TL-10: "AFK periods shown as greyed-out gaps." Backend already filters out AFK events, so the timeline does not contain AFK *events*. To show "greyed-out gaps" you would need either:
  - Backend to return AFK *periods* as a separate list (e.g. `afk_periods: { start, end }[]`) and the frontend to render them as grey segments on the timeline, or
  - Defer to a later WP and for WP-3 only show the (already AFK-filtered) events as blocks. Gaps between blocks are then "unrecorded" or "AFK/other"; no need to label them as AFK yet.
- **Recommendation for WP-3:** Omit explicit AFK segments. Timeline shows only non-AFK events; gaps between blocks are implicit. Add F-TL-10 in a later iteration if desired.

---

## Technical notes

- **Time zone:** Backend returns timestamps in UTC. Frontend should display in the user’s local time (e.g. `new Date(event.timestamp)` and format with `Intl` or a small formatter).
- **Duration format:** e.g. `formatDuration(seconds)` → "5m", "1h 20m", "45s".
- **App color:** For unlabeled events, use a deterministic color from `event.data.app` (e.g. hash string to index into a palette of 8–10 colors) so the same app is always the same color on the timeline.
- **Responsiveness:** Timeline bar can use CSS (flex/grid) or a simple calculation: `left = (eventStart - dayStart) / dayDuration * 100%`, `width = eventDuration / dayDuration * 100%`. Use percentage or `position: absolute` inside a relative container.

---

## Testing Plan

| # | Test | How to verify |
|---|------|---------------|
| 1 | Date defaults to today, timeline loads | Open app; main area shows timeline + list for today; no console errors |
| 2 | Timeline shows event blocks | Events appear as colored segments; order matches time |
| 3 | Event list matches timeline | Same events in list; app, title, start time, duration visible |
| 4 | Prev/Next day changes date and reloads | Click ◀; date and events update; click ▶; back to today or next day |
| 5 | "Today" resets to current day | After navigating away, click Today; date is today, events refetched |
| 6 | Date picker changes date | Select another day; timeline and list update for that day |
| 7 | Labeled events visually distinct | If any events have `session_id`, they show workflow color (border/badge) on timeline and in list |
| 8 | Empty day shows message | Pick a future date or a day with no AW data; friendly empty state |
| 9 | API failure shows error | With backend stopped or wrong URL; error state and optionally retry |

---

## Definition of Done

- [ ] Timeline store or composable fetches `/api/v1/timeline?date=YYYY-MM-DD` and exposes events, loading, error.
- [ ] Shell main content shows Timeline view (timeline bar + event list).
- [ ] Date navigation: Today, prev day, next day, and date picker; changing date refetches and updates timeline.
- [ ] Timeline bar: one block per event, positioned by time, colored by app (or workflow if labeled).
- [ ] Event list: table or cards with app, title, URL, start time, duration; labeled events show workflow badge.
- [ ] Loading and error states handled; empty day shows a clear message.
- [ ] All 9 tests pass.
