from datetime import date

from fastapi import APIRouter, HTTPException, Query

from ..models import Workflow, WorkflowCreate, WorkflowStats, WorkflowUpdate
from ..services import workflow_service

router = APIRouter(prefix="/api/v1", tags=["workflows"])


@router.get("/workflows", response_model=list[Workflow])
def list_workflows(
    archived: bool = Query(False, description="Include archived workflows"),
):
    return workflow_service.list_workflows(include_archived=archived)


@router.post("/workflows", response_model=Workflow)
def create_workflow(body: WorkflowCreate):
    return workflow_service.create_workflow(body)


@router.get("/workflows/{wf_id}", response_model=Workflow)
def get_workflow(wf_id: str):
    w = workflow_service.get_workflow(wf_id)
    if w is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return w


@router.put("/workflows/{wf_id}", response_model=Workflow)
def update_workflow(wf_id: str, body: WorkflowUpdate):
    w = workflow_service.update_workflow(wf_id, body)
    if w is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return w


@router.delete("/workflows/{wf_id}", status_code=204)
def archive_workflow(wf_id: str):
    if not workflow_service.archive_workflow(wf_id):
        raise HTTPException(status_code=404, detail="Workflow not found")


@router.get("/workflows/{wf_id}/stats", response_model=WorkflowStats)
def get_workflow_stats(
    wf_id: str,
    start: str | None = Query(None, description="Start date YYYY-MM-DD"),
    end: str | None = Query(None, description="End date YYYY-MM-DD"),
):
    """Return time breakdown for a composite workflow across its child sessions."""
    start_date = date.fromisoformat(start) if start else None
    end_date = date.fromisoformat(end) if end else None
    stats = workflow_service.get_workflow_stats(wf_id, start_date, end_date)
    if stats is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return stats
