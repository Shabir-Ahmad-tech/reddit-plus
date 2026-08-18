"""
Opportunity Inbox Router — Primary Core of Reddit Plus v2.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any

from src.database.session import get_db
from src.database.repositories.match_repository import MatchRepository
from src.database.repositories.analysis_repository import AnalysisRepository
from src.database.repositories.comment_repository import CommentRepository
from src.intelligence import IntentClassifier, PostAnalyzer, OpportunityScorer
from src.reddit import CommentFetcher, RedditClient

router = APIRouter(prefix="/opportunities", tags=["Opportunities"])


def serialize_opportunity(match) -> Dict[str, Any]:
    post = match.post
    opp = match.opportunity
    analysis = post.analysis if post else None
    rule = match.rule
    replies = match.reply_drafts or []

    # Comments summary
    comments = []
    if post and post.comments:
        comments = [
            {
                "id": c.id,
                "reddit_id": c.reddit_id,
                "author": c.author,
                "score": c.score,
                "body": c.body,
                "posted_at": c.posted_at.isoformat() if c.posted_at else None,
            }
            for c in post.comments[:5]
        ]

    # Reply drafts summary
    reply_list = [
        {
            "id": r.id,
            "strategy": r.strategy,
            "content": r.content,
            "model_used": r.model_used,
            "status": r.status,
            "promotion_risk": r.promotion_risk,
            "critic_scorecard": r.critic_scorecard or {},
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in replies
    ]

    return {
        "id": match.id,
        "workspace_id": match.workspace_id,
        "rule_id": match.rule_id,
        "rule_name": rule.name if rule else "General Match",
        "status": match.status,
        "match_score": match.match_score,
        "match_reasons": match.match_reasons or [],
        "created_at": match.created_at.isoformat() if match.created_at else None,
        # Reddit post
        "post": {
            "id": post.id if post else None,
            "reddit_id": post.reddit_id if post else None,
            "subreddit": post.subreddit if post else None,
            "title": post.title if post else None,
            "body": post.body if post else None,
            "author": post.author if post else None,
            "score": post.score if post else 0,
            "num_comments": post.num_comments if post else 0,
            "upvote_ratio": post.upvote_ratio if post else 0.0,
            "post_flair": post.post_flair if post else None,
            "post_type": post.post_type if post else "text",
            "url": post.url if post else None,
            "permalink": post.permalink if post else None,
            "posted_at": post.posted_at.isoformat() if post and post.posted_at else None,
        } if post else None,
        # Opportunity score breakdown
        "opportunity": {
            "total_score": opp.total_score if opp else int(match.match_score),
            "relevance_score": opp.relevance_score if opp else match.match_score,
            "buying_signal_score": opp.buying_signal_score if opp else 0.0,
            "pain_score": opp.pain_score if opp else 0.0,
            "urgency_score": opp.urgency_score if opp else 0.0,
            "engagement_score": opp.engagement_score if opp else 0.0,
            "freshness_score": opp.freshness_score if opp else 0.0,
            "community_fit_score": opp.community_fit_score if opp else 0.0,
            "recommended_action": opp.recommended_action if opp else "Monitor",
        } if opp else None,
        # Deep AI Analysis
        "analysis": {
            "summary": analysis.summary,
            "what_it_means": analysis.what_it_means,
            "what_it_requires": analysis.what_it_requires,
            "urgency": analysis.urgency,
            "sentiment": analysis.sentiment,
            "intent_tag": analysis.intent_tag,
            "intent_confidence": analysis.intent_confidence,
            "buy_signal_strength": analysis.buy_signal_strength,
            "pain_strength": analysis.pain_strength,
            "engagement_potential": analysis.engagement_potential,
            "mentioned_products": analysis.mentioned_products or [],
            "pain_keywords": analysis.pain_keywords or [],
            "requirements": analysis.requirements or [],
            "goals": analysis.goals or [],
            "competitors": analysis.competitors or [],
            "recommended_angle": analysis.recommended_angle,
            "reddit_context": analysis.reddit_context,
            "community_signals": analysis.community_signals,
            "is_fallback": analysis.is_fallback,
        } if analysis else None,
        "comments": comments,
        "replies": reply_list,
        "latest_reply": reply_list[0] if reply_list else None,
    }


@router.get("")
def list_opportunities(
    rule_id: Optional[int] = None,
    status: Optional[str] = None,
    min_score: Optional[int] = None,
    intent: Optional[str] = None,
    subreddit: Optional[str] = None,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List opportunities for the Opportunity Inbox."""
    match_repo = MatchRepository(db)
    matches, total = match_repo.get_opportunities(
        rule_id=rule_id,
        status=status,
        min_opportunity=min_score,
        intent=intent,
        subreddit=subreddit,
        limit=limit,
        offset=offset,
    )

    items = [serialize_opportunity(m) for m in matches]
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{match_id}")
def get_opportunity_detail(match_id: int, db: Session = Depends(get_db)):
    """Get single opportunity with all signals and comments."""
    match_repo = MatchRepository(db)
    match = match_repo.get_by_id(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return serialize_opportunity(match)


@router.patch("/{match_id}/status")
def update_opportunity_status(
    match_id: int,
    status: str = Query(..., enum=["new", "saved", "ignored", "replied", "archived"]),
    db: Session = Depends(get_db),
):
    """Update opportunity triage status."""
    match_repo = MatchRepository(db)
    match = match_repo.update_status(match_id, status)
    if not match:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return {"success": True, "id": match.id, "status": match.status}


@router.post("/{match_id}/analyze")
async def analyze_opportunity_on_demand(match_id: int, db: Session = Depends(get_db)):
    """Run or re-run deep AI intelligence and scoring on demand."""
    match_repo = MatchRepository(db)
    analysis_repo = AnalysisRepository(db)
    comment_repo = CommentRepository(db)

    match = match_repo.get_by_id(match_id)
    if not match or not match.post:
        raise HTTPException(status_code=404, detail="Opportunity or post not found")

    post = match.post

    # Ingest top comments if none exist
    top_comments = []
    if post.num_comments and post.num_comments > 0 and not post.comments:
        try:
            client = RedditClient()
            cf = CommentFetcher(client)
            norm_comments = await cf.fetch_post_comments(post.subreddit, post.reddit_id, limit=5)
            for nc in norm_comments:
                c, _ = comment_repo.upsert_comment(
                    reddit_id=nc.reddit_id,
                    post_id=post.id,
                    body=nc.body,
                    author=nc.author,
                    score=nc.score,
                    permalink=nc.permalink,
                    posted_at=nc.posted_at,
                )
                top_comments.append(c)
        except Exception:
            pass

    # Run AI pipelines
    ic = IntentClassifier()
    pa = PostAnalyzer()

    intent_res = await ic.classify(post.body or "", post.title)
    deep_res = await pa.analyze(post, top_comments=top_comments)

    analysis = analysis_repo.save_analysis(
        post_id=post.id,
        summary=deep_res.summary,
        what_it_means=deep_res.what_it_means,
        what_it_requires=deep_res.what_it_requires,
        urgency=deep_res.urgency,
        sentiment=deep_res.sentiment,
        intent_tag=intent_res.tag,
        intent_confidence=intent_res.confidence,
        buy_signal_strength=deep_res.buy_signal_strength,
        pain_strength=deep_res.pain_strength,
        engagement_potential=deep_res.engagement_potential,
        mentioned_products=deep_res.mentioned_products,
        pain_keywords=deep_res.pain_keywords,
        requirements=deep_res.requirements,
        goals=deep_res.goals,
        competitors=deep_res.competitors,
        recommended_angle=deep_res.recommended_angle,
        reddit_context=deep_res.reddit_context,
        community_signals=deep_res.community_signals,
        is_fallback=deep_res.is_fallback,
    )

    opp_breakdown = OpportunityScorer.calculate(match, post, analysis)
    analysis_repo.save_opportunity_score(
        match_id=match.id,
        total_score=opp_breakdown.total_score,
        relevance_score=opp_breakdown.relevance_score,
        buying_signal_score=opp_breakdown.buying_signal_score,
        pain_score=opp_breakdown.pain_score,
        urgency_score=opp_breakdown.urgency_score,
        engagement_score=opp_breakdown.engagement_score,
        freshness_score=opp_breakdown.freshness_score,
        community_fit_score=opp_breakdown.community_fit_score,
        recommended_action=opp_breakdown.recommended_action,
    )

    # Reload fresh record
    refreshed = match_repo.get_by_id(match_id)
    return serialize_opportunity(refreshed)
