"""
Legacy API Compatibility Layer.
Maps v1 endpoints to ensure backward compatibility with earlier clients.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from src.database.session import get_db
from src.database.repositories.match_repository import MatchRepository
from src.database.repositories.rule_repository import RuleRepository
from src.api.v1.opportunities import serialize_opportunity
from src.api.v1.dashboard import get_dashboard_metrics
from src.jobs.runner import job_runner, activity_logs

legacy_router = APIRouter(prefix="/api", tags=["Legacy Compatibility"])


@legacy_router.get("/stats")
def legacy_stats(db: Session = Depends(get_db)):
    metrics = get_dashboard_metrics(db)
    return {
        "total_mentions": metrics["total_posts"],
        "actionable_leads": metrics["high_opportunities"],
        "active_keywords": metrics["active_rules"],
        "by_intent_tag": metrics["intent_distribution"],
        "top_subreddits": metrics["top_subreddits"],
        "scheduler": {
            "is_running": metrics["job_runner"]["is_running"],
            "last_poll_time": metrics["job_runner"]["last_run_time"],
        },
    }


@legacy_router.get("/mentions")
def legacy_mentions(
    tag: Optional[str] = None,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    match_repo = MatchRepository(db)
    matches, total = match_repo.get_opportunities(intent=tag, limit=limit, offset=offset)
    return {
        "items": [serialize_opportunity(m) for m in matches],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@legacy_router.get("/keywords")
def legacy_keywords(db: Session = Depends(get_db)):
    rule_repo = RuleRepository(db)
    rules = rule_repo.get_all()
    out = []
    for r in rules:
        out.append({
            "id": r.id,
            "keyword": r.name,
            "subreddits": [s.subreddit_name for s in (r.rule_subreddits or [])],
            "active": r.is_active,
            "min_score": r.min_score,
        })
    return out


@legacy_router.post("/scheduler/trigger-poll")
@legacy_router.post("/scheduler/trigger-cycle")
async def legacy_trigger():
    results = await job_runner.run_full_cycle()
    return {"success": True, "results": results}


@legacy_router.get("/scheduler/status")
def legacy_scheduler_status():
    return {
        "is_running": job_runner.is_running,
        "last_run_time": job_runner.last_run_time.isoformat() if job_runner.last_run_time else None,
        "stats": job_runner.stats,
    }


@legacy_router.get("/logs")
def legacy_logs(limit: int = 100):
    return list(activity_logs)[-limit:]
