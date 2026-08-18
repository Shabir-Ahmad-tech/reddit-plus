"""
Monitoring Rules Router.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any

from src.database.session import get_db
from src.database.models import Workspace
from src.database.repositories.rule_repository import RuleRepository
from src.api.schemas.models import MonitoringRuleCreate, MonitoringRuleUpdate, KeywordExpandRequest
from src.intelligence.keyword_expander import KeywordExpander

router = APIRouter(prefix="/monitoring-rules", tags=["Monitoring Rules"])


def serialize_rule(rule) -> Dict[str, Any]:
    return {
        "id": rule.id,
        "workspace_id": rule.workspace_id,
        "name": rule.name,
        "description": rule.description,
        "is_active": rule.is_active,
        "min_score": rule.min_score,
        "min_comments": rule.min_comments,
        "min_opportunity_score": rule.min_opportunity_score,
        "max_age_hours": rule.max_age_hours,
        "target_intents": rule.target_intents or [],
        "keywords": [k.keyword for k in (rule.keywords or [])],
        "subreddits": [s.subreddit_name for s in (rule.rule_subreddits or [])],
        "exclusions": [e.pattern for e in (rule.exclusions or [])],
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
    }


@router.get("")
def list_rules(db: Session = Depends(get_db)):
    """List all monitoring rules."""
    rule_repo = RuleRepository(db)
    rules = rule_repo.get_all()
    return [serialize_rule(r) for r in rules]


@router.post("")
def create_rule(req: MonitoringRuleCreate, db: Session = Depends(get_db)):
    """Create a new monitoring rule."""
    rule_repo = RuleRepository(db)

    # Get default workspace
    ws = db.query(Workspace).first()
    workspace_id = ws.id if ws else 1

    rule = rule_repo.create_rule(
        workspace_id=workspace_id,
        name=req.name,
        description=req.description,
        keywords=req.keywords,
        subreddits=req.subreddits,
        exclusions=req.exclusions,
        min_score=req.min_score,
        min_comments=req.min_comments,
        min_opportunity_score=req.min_opportunity_score,
        max_age_hours=req.max_age_hours,
        target_intents=req.target_intents,
        notify_ntfy=req.notify_ntfy,
        notify_email=req.notify_email,
        notify_webhook=req.notify_webhook,
    )
    return serialize_rule(rule)


@router.get("/{rule_id}")
def get_rule(rule_id: int, db: Session = Depends(get_db)):
    """Get single rule detail."""
    rule_repo = RuleRepository(db)
    rule = rule_repo.get_by_id(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return serialize_rule(rule)


@router.patch("/{rule_id}")
def update_rule(rule_id: int, req: MonitoringRuleUpdate, db: Session = Depends(get_db)):
    """Toggle or update a monitoring rule."""
    rule_repo = RuleRepository(db)
    rule = rule_repo.get_by_id(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if req.is_active is not None:
        rule.is_active = req.is_active
    if req.name is not None:
        rule.name = req.name
    if req.min_score is not None:
        rule.min_score = req.min_score
    if req.min_opportunity_score is not None:
        rule.min_opportunity_score = req.min_opportunity_score

    db.commit()
    return serialize_rule(rule)


@router.delete("/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    """Delete a monitoring rule."""
    rule_repo = RuleRepository(db)
    deleted = rule_repo.delete(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"success": True, "message": "Rule deleted"}


@router.post("/expand-keywords")
async def expand_keywords(req: KeywordExpandRequest):
    """AI keyword expansion tool to suggest related terms."""
    expander = KeywordExpander()
    suggestions = await expander.expand(req.seed)
    return {"seed": req.seed, "suggestions": suggestions}
