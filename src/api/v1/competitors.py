"""
Competitor Intelligence Router.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any

from src.database.session import get_db
from src.database.models import Workspace
from src.database.repositories.competitor_repository import CompetitorRepository
from src.database.repositories.rule_repository import RuleRepository
from src.api.schemas.models import CompetitorCreate

router = APIRouter(prefix="/competitors", tags=["Competitors"])


@router.get("")
def list_competitors(db: Session = Depends(get_db)):
    """List tracked competitors."""
    comp_repo = CompetitorRepository(db)
    comps = comp_repo.get_all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "website": c.website,
            "tracked_keywords": c.tracked_keywords or [],
            "auto_rule_id": c.auto_rule_id,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in comps
    ]


@router.post("")
def add_competitor(req: CompetitorCreate, db: Session = Depends(get_db)):
    """Add a competitor and auto-generate monitoring rules for competitor complaints/alternatives."""
    comp_repo = CompetitorRepository(db)
    rule_repo = RuleRepository(db)

    ws = db.query(Workspace).first()
    workspace_id = ws.id if ws else 1

    # Create competitor with auto generated keywords
    comp = comp_repo.create_competitor(
        workspace_id=workspace_id,
        name=req.name,
        website=req.website,
        tracked_keywords=req.tracked_keywords,
    )

    # Auto create a monitoring rule for this competitor
    rule = rule_repo.create_rule(
        workspace_id=workspace_id,
        name=f"Competitor: {comp.name}",
        description=f"Auto-generated rule tracking complaints and alternatives to {comp.name}",
        keywords=comp.tracked_keywords,
        min_score=1,
        min_opportunity_score=65,
        target_intents=["competitor-complaint", "seeking-alternatives", "pain-point", "buy-intent"],
    )
    comp.auto_rule_id = rule.id
    db.commit()

    return {
        "id": comp.id,
        "name": comp.name,
        "website": comp.website,
        "tracked_keywords": comp.tracked_keywords,
        "auto_rule_id": comp.auto_rule_id,
    }


@router.delete("/{competitor_id}")
def delete_competitor(competitor_id: int, db: Session = Depends(get_db)):
    """Delete a tracked competitor."""
    comp_repo = CompetitorRepository(db)
    rule_repo = RuleRepository(db)

    comp = comp_repo.get_by_id(competitor_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Competitor not found")

    if comp.auto_rule_id:
        rule_repo.delete(comp.auto_rule_id)

    comp_repo.delete(competitor_id)
    return {"success": True, "message": "Competitor deleted"}
