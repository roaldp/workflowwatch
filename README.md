# WorkflowWatch

**Detect workflows.** ActivityWatch plus a workflow-detection and labeling layer — same local-first, privacy-preserving base, with manual and suggested labeling of events into workflows.

This repository is a fork of [ActivityWatch](https://github.com/ActivityWatch/activitywatch). It adds the **WorkflowWatch** app (FastAPI backend + Vue frontend) in the [`workflowwatch/`](./workflowwatch) directory.

## Quick start

1. **Run ActivityWatch** (tracks apps, browser, AFK). See [ActivityWatch docs](https://docs.activitywatch.net) or [README-activitywatch.md](./README-activitywatch.md).
2. **Run the WorkflowWatch app** (label events into workflows, view timeline, manage sessions):

   ```bash
   cd workflowwatch
   source .venv/bin/activate
   WW_DB_PATH=./data/workflowwatch.db python -m uvicorn backend.main:app --host 127.0.0.1 --port 5700
   ```

   In another terminal:

   ```bash
   cd workflowwatch/frontend
   npm install && npm run dev
   ```

   Open http://localhost:5173.

Full run instructions: [workflowwatch/README.md](./workflowwatch/README.md).

## Repository layout

| Path | Description |
|------|-------------|
| **Root** | ActivityWatch bundle (submodules: aw-server, aw-qt, watchers, etc.). Unchanged from upstream except for the addition of `workflowwatch/`. |
| **[workflowwatch/](./workflowwatch)** | WorkflowWatch app: backend (FastAPI, SQLite), frontend (Vue), workplans. Requires ActivityWatch running on `localhost:5600`. |
| **[README-activitywatch.md](./README-activitywatch.md)** | Original ActivityWatch README (about, installation, architecture). |

## Upstream sync

To pull changes from ActivityWatch:

```bash
git fetch upstream
git merge upstream/master
git push origin master
```

## License

Same as ActivityWatch (see [LICENSE.txt](./LICENSE.txt)). WorkflowWatch additions are offered under the same terms.
