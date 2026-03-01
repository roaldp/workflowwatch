"""
Label rules endpoints.
Manages user-defined deterministic labeling rules (Tier 0 of auto-label pipeline).
"""

from fastapi import APIRouter, HTTPException

from ..models import LabelRule, LabelRuleCreate
from ..services import rule_service

router = APIRouter(prefix="/api/v1/label-rules", tags=["label-rules"])


@router.get("", response_model=list[LabelRule])
def list_rules():
    return rule_service.get_rules()


@router.post("", response_model=LabelRule, status_code=201)
def create_rule(body: LabelRuleCreate):
    if body.rule_type not in ("app", "title_keyword"):
        raise HTTPException(400, "rule_type must be 'app' or 'title_keyword'")
    if not body.match_value.strip():
        raise HTTPException(400, "match_value cannot be empty")
    return rule_service.create_rule(body.workflow_id, body.rule_type, body.match_value.strip())


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: str):
    if not rule_service.delete_rule(rule_id):
        raise HTTPException(404, "Rule not found")
