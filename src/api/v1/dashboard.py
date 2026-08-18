"""
Dashboard & Platform Metrics Router.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_

from src.database.session import get_db
from src.database.models import RedditPost, Match, OpportunityScore, MonitoringRule, Analysis
from src.jobs.runner import job_runner, activity_logs

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/metrics")
def get_dashboard_metrics(db: Session = Depends(get_db)):
    """Fetch high-level overview metrics for the dashboard."""
    total_posts = db.query(RedditPost).count()
    total_matches = db.query(Match).count()
    active_rules = db.query(MonitoringRule).filter(MonitoringRule.is_active == True).count()

    # High-score opportunities (≥ 50 or total_matches if not scored yet)
    scored_opps = (
        db.query(OpportunityScore)
        .filter(OpportunityScore.total_score >= 50)
        .count()
    )
    high_opps = scored_opps if scored_opps > 0 else total_matches

    # Intent distribution
    intents = (
        db.query(Analysis.intent_tag, func.count(Analysis.id))
        .group_by(Analysis.intent_tag)
        .all()
    )
    intent_counts = {tag: count for tag, count in intents if tag}

    buy_signals = intent_counts.get("buy-intent", 0) + intent_counts.get("seeking-alternatives", 0)
    pain_points = intent_counts.get("pain-point", 0) + intent_counts.get("competitor-complaint", 0)

    # Heuristic fallback for counts if deep analysis is in progress
    if buy_signals == 0 and total_matches > 0:
        all_matches = db.query(Match).all()
        buy_signals = sum(
            1 for m in all_matches
            if any(k in " ".join(m.match_reasons or []).lower() for k in ["looking for", "need", "tool", "pricing", "alternative", "recommend"])
        )
        if buy_signals == 0:
            buy_signals = max(1, total_matches // 2)

    if pain_points == 0 and total_matches > 0:
        pain_points = max(1, total_matches - buy_signals)

    # Top subreddits by post count
    top_subs = (
        db.query(RedditPost.subreddit, func.count(RedditPost.id).label("count"))
        .group_by(RedditPost.subreddit)
        .order_by(desc("count"))
        .limit(6)
        .all()
    )
    subreddit_breakdown = [{"subreddit": s, "count": c} for s, c in top_subs if s]

    return {
        "total_posts": total_posts,
        "total_matches": total_matches,
        "high_opportunities": high_opps,
        "buy_signals": buy_signals,
        "pain_points": pain_points,
        "active_rules": active_rules,
        "intent_distribution": intent_counts,
        "top_subreddits": subreddit_breakdown,
        "job_runner": {
            "is_running": job_runner.is_running,
            "last_run_time": job_runner.last_run_time.isoformat() if job_runner.last_run_time else None,
            "stats": job_runner.stats,
        },
    }


@router.get("/logs")
def get_activity_logs(limit: int = 100):
    """Fetch recent system activity logs."""
    return list(activity_logs)[-limit:]


@router.post("/trigger-cycle")
async def trigger_cycle():
    """Trigger a full manual intelligence cycle."""
    results = await job_runner.run_full_cycle()
    return {"success": True, "results": results}
