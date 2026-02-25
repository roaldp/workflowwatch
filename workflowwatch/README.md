# WorkflowWatch app

Workflow-specific time tracking on top of ActivityWatch. Manual labeling of events into workflows; backend + frontend for v1.

## Run

**1. Backend** (requires ActivityWatch running on `localhost:5600`). From the **repository root**:

```bash
cd workflowwatch
source .venv/bin/activate
WW_DB_PATH=./data/workflowwatch.db python -m uvicorn backend.main:app --host 127.0.0.1 --port 5700
```

**2. Frontend** (new terminal). From the **repository root**:

```bash
cd workflowwatch/frontend
npm install
npm run dev
```

Open **http://localhost:5173**.

## Development

Use `--reload` for the backend so code changes (including new API routes) are picked up without manually restarting. From `workflowwatch/`:

```bash
WW_DB_PATH=./data/workflowwatch.db python -m uvicorn backend.main:app --host 127.0.0.1 --port 5700 --reload
```

If you add or change backend code (e.g. a new workplan) and don’t use `--reload`, restart the backend once so the new routes are loaded.
