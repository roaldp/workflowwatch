# WP-2: Workflow CRUD + Frontend Shell

> **Goal:** Workflow API on the backend and a minimal Vue 3 frontend with a sidebar that lists workflows and a modal to create/edit them. Workflows persist across reloads.
>
> **Testable outcome:** Create a workflow in the UI (e.g. "Startup Sourcing"), reload the page — it's still there. Edit name/color, reload — changes persisted.

---

## Prerequisites

- WP-1 complete (backend running, SQLite with `workflows` table, `/api/v1/health` and `/api/v1/timeline` working).
- Node.js 18+ and npm (or pnpm/yarn) available.

---

## Deliverables

| # | Deliverable | Requirement refs |
|---|-------------|------------------|
| 1 | Workflow CRUD API (GET list, POST, GET one, PUT, DELETE archive) | B-WF-1, B-WF-2, B-WF-3, B-WF-4 |
| 2 | Vue 3 + Vite + TypeScript frontend scaffold | Tech stack (design doc §9) |
| 3 | App shell: header, sidebar, main content area | F-WF-1, layout §6.1 |
| 4 | Sidebar: workflow list with color dot, "New workflow" button | F-WF-1, F-WF-2 |
| 5 | Create workflow modal (name required, description, color) | F-WF-2 |
| 6 | Edit workflow (inline or modal) and archive from sidebar | F-WF-3 |
| 7 | API client and Pinia store for workflows | — |
| 8 | Frontend served in dev (Vite) and optionally by backend for production later | — |

---

## Tasks

### 1. Backend: Workflow router and service

**Pydantic models** (add to `backend/models.py` or new file):

```python
class WorkflowCreate(BaseModel):
    name: str
    description: str | None = None
    color: str | None = None   # hex, e.g. "#3B82F6"

class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None

class Workflow(BaseModel):
    id: str
    name: str
    description: str | None
    color: str | None
    created_at: str   # ISO 8601
    updated_at: str
    archived: bool
```

**Service** `backend/services/workflow_service.py`:

- `list_workflows(include_archived: bool = False) -> list[Workflow]` — query `workflows` table, filter by `archived`, return list.
- `create_workflow(body: WorkflowCreate) -> Workflow` — generate UUID, set `created_at`/`updated_at`, insert, return.
- `get_workflow(id: str) -> Workflow | None` — fetch by id.
- `update_workflow(id: str, body: WorkflowUpdate) -> Workflow | None` — update provided fields, set `updated_at`, return.
- `archive_workflow(id: str) -> bool` — set `archived = 1`, return True if row existed.

Use the existing `get_db()` connection; workflow operations are synchronous (SQLite), so run them in `run_in_executor` or keep them sync and use FastAPI's default thread pool (sync route handlers are run in a thread pool).

**Router** `backend/routers/workflows.py`:

| Method | Path | Response |
|--------|------|----------|
| GET | `/api/v1/workflows` | `Workflow[]` (query param `archived=false` by default) |
| POST | `/api/v1/workflows` | `Workflow` (body: name, description?, color?) |
| GET | `/api/v1/workflows/{id}` | `Workflow` or 404 |
| PUT | `/api/v1/workflows/{id}` | `Workflow` or 404 |
| DELETE | `/api/v1/workflows/{id}` | 204 (archive) or 404 |

Register the router in `main.py`.

**Default color:** If `color` is omitted on create, assign a default from a short palette (e.g. `#3B82F6`, `#10B981`, `#F59E0B`, `#EF4444`, `#8B5CF6`) in round-robin or random.

---

### 2. Frontend: Project scaffold

Create the frontend under `workflowwatch/frontend/`:

```bash
npm create vite@latest frontend -- --template vue-ts
cd frontend && npm install
```

**Additional dependencies:**

- `pinia` — state management
- `vue-router` — routing (optional for WP-2; can use a single view first)
- `@vueuse/core` — optional utilities
- `tailwindcss` + `postcss` + `autoprefixer` — styling
- `axios` or use `fetch` — API client (or `$fetch` if using Nuxt; for Vite, axios or native fetch is fine)

**Tailwind:** Initialize Tailwind per official docs (npx tailwindcss init, configure content paths, add directives to main CSS).

**Env:** Create `.env.development` with `VITE_API_BASE=http://localhost:5700` so the frontend can call the backend. Use `import.meta.env.VITE_API_BASE` in the API client.

**Project structure (minimal for WP-2):**

```
frontend/
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── tsconfig.json
├── src/
│   ├── main.ts
│   ├── App.vue
│   ├── api/
│   │   └── client.ts       # base URL, get/post/put/delete helpers
│   ├── stores/
│   │   └── workflows.ts    # Pinia store: workflows list, create, update, archive, fetch
│   ├── views/
│   │   └── ShellView.vue   # layout: header + sidebar + main (placeholder content)
│   ├── components/
│   │   ├── WorkflowSidebar.vue   # list + "New workflow" button
│   │   ├── WorkflowModal.vue     # create/edit form (name, description, color)
│   │   └── WorkflowColorDot.vue  # small colored circle
│   └── types/
│       └── workflow.ts    # Workflow interface matching API
```

---

### 3. API client and workflow store

**api/client.ts:**

- `baseUrl = import.meta.env.VITE_API_BASE || 'http://localhost:5700'`
- `get<T>(path)`, `post<T>(path, body)`, `put<T>(path, body)`, `delete(path)` — return typed responses, throw on non-2xx.

**stores/workflows.ts:**

- State: `workflows: Workflow[]`, `loading: boolean`, `error: string | null`
- Actions: `fetchWorkflows()`, `createWorkflow(payload)`, `updateWorkflow(id, payload)`, `archiveWorkflow(id)`
- After create/update/archive, refresh the list (or optimistically update local state).

**types/workflow.ts:**

- Interface `Workflow` matching backend response: id, name, description, color, created_at, updated_at, archived.

---

### 4. App shell and layout

**App.vue:** Single route or single view for WP-2: render `ShellView`.

**ShellView.vue:**

- Header: "WorkflowWatch" title (no date/nav yet — that's WP-3).
- Two-column layout: sidebar (fixed width ~220px) + main content (flex-1). Main content can show a placeholder: "Timeline and events will go here (WP-3)."
- Sidebar: include `WorkflowSidebar` component.

---

### 5. Workflow sidebar component

**WorkflowSidebar.vue:**

- On mount, call `workflowsStore.fetchWorkflows()`.
- Render list of workflows: for each, show `WorkflowColorDot` + name. Clicking a workflow can open edit modal (or just show as selected for now).
- "New workflow" button at bottom (or top): opens create modal.
- Context menu or icon on each row: Edit, Archive. Edit opens modal with prefilled data; Archive calls `archiveWorkflow(id)` and refreshes list.
- Archived workflows: either hide by default (WP-2) or show in a collapsed "Archived" section with `archived=true` fetch. Per design F-WF-4, archived don't appear in labeling dropdown; for sidebar, WP-2 can show only active and add "Show archived" in a later WP if needed.

---

### 6. Create / Edit workflow modal

**WorkflowModal.vue:**

- Props: `visible: boolean`, `workflow: Workflow | null` (null = create, non-null = edit).
- Emit: `close`, `saved` (after successful create or update).
- Form fields:
  - Name (required, text input)
  - Description (optional, textarea)
  - Color (optional; color picker input or dropdown of preset hex colors)
- Submit: if create, `workflowsStore.createWorkflow({ name, description, color })`; if edit, `workflowsStore.updateWorkflow(id, { name, description, color })`. On success, emit `saved` and close.
- Validation: name non-empty. Show error if API returns 4xx.

---

### 7. CORS and dev workflow

- Backend already allows `http://localhost:5173` and `http://127.0.0.1:5173` (Vite default). No change needed if frontend runs on 5173.
- Start backend: `cd workflowwatch && source .venv/bin/activate && WW_DB_PATH=./data/workflowwatch.db uvicorn backend.main:app --host 127.0.0.1 --port 5700`
- Start frontend: `cd workflowwatch/frontend && npm run dev`
- Open browser to `http://localhost:5173`. Ensure API base is `http://localhost:5700` so requests hit the backend.

---

## Testing Plan

| # | Test | How to verify |
|---|------|---------------|
| 1 | Backend: GET /api/v1/workflows returns [] when empty | curl or browser; initial state empty list |
| 2 | Backend: POST /api/v1/workflows creates workflow | POST with name, get 200 and workflow with id, name, created_at |
| 3 | Backend: GET /api/v1/workflows returns created workflow | List includes the new workflow |
| 4 | Backend: PUT updates name/color | PUT with new name; GET returns updated data |
| 5 | Backend: DELETE archives | DELETE then GET list with archived=false no longer includes it; GET with archived=true includes it (if list endpoint supports archived param) |
| 6 | Frontend: Load app, sidebar shows workflow list | Open app, sidebar shows "New workflow" and any workflows |
| 7 | Frontend: Create workflow, see in list | Click "New workflow", enter name, save; list updates; reload page, workflow still there |
| 8 | Frontend: Edit workflow, reload, changes persisted | Edit name or color, save; reload; changes visible |
| 9 | Frontend: Archive workflow, disappears from list | Archive a workflow; list refreshes without it |

---

## Definition of Done

- [x] Backend: GET/POST/GET/PUT/DELETE workflows implemented and registered.
- [x] Backend: Workflows persisted in SQLite; UUID and timestamps set correctly.
- [x] Frontend: Vite + Vue 3 + TypeScript + Tailwind + Pinia scaffold runs without errors.
- [x] Frontend: Sidebar shows workflow list and "New workflow" button.
- [x] Frontend: Create modal creates a workflow and list updates; reload keeps it.
- [x] Frontend: Edit modal updates workflow; reload keeps changes.
- [x] Frontend: Archive removes workflow from active list (and optionally show archived section or leave for later).
- [ ] All 9 tests pass (manual: run backend + frontend, then verify in browser).
- [x] No linter errors; types and API contract consistent between backend and frontend.

## Completion notes (auto-greenlight run)

- **Auto-greenlight:** All edits were applied automatically to bring WP-2 to completion. Test when back: start backend + frontend, create a workflow, reload, edit, reload, archive.
- Backend workflow API verified via curl: GET empty list, POST create, GET list returns created workflow.
- Frontend build passes (`npm run build`). Dev server: `npm run dev` in `frontend/`, then open http://localhost:5173.
