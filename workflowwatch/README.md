# WorkflowWatch app

Workflow-specific time tracking on top of ActivityWatch. Manual labeling of events into workflows; backend + frontend for v1.

## First-time setup

From the repo root (`baghdad/`):

```bash
python3.12 -m venv workflowwatch/.venv
source workflowwatch/.venv/bin/activate
pip install -r workflowwatch/backend/requirements.txt
```

## Run

Requires ActivityWatch running on `localhost:5600`.

**Terminal 1 — Backend:**
```bash
cd /path/to/baghdad
source workflowwatch/.venv/bin/activate
WW_DB_PATH=workflowwatch/data/workflowwatch.db python -m uvicorn backend.main:app --host 127.0.0.1 --port 5700 --reload --app-dir workflowwatch
```

**Terminal 2 — Frontend:**
```bash
cd /path/to/baghdad/workflowwatch/frontend
npm run dev
```

Open **http://localhost:5173**.
