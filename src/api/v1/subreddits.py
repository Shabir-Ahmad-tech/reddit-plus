"""
Subreddits Directory and Community Profiles Router.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any

from src.database.session import get_db
from src.database.repositories.subreddit_repository import SubredditRepository
from src.api.schemas.models import SubredditCreate, SubredditProfileUpdate
from src.reddit import RedditClient

router = APIRouter(prefix="/subreddits", tags=["Subreddits"])


def serialize_subreddit(sub) -> Dict[str, Any]:
    profile = sub.profile
    return {
        "id": sub.id,
        "name": sub.name,
        "display_name": sub.display_name or f"r/{sub.name}",
        "title": sub.title,
        "description": sub.description,
        "subscribers": sub.subscribers,
        "over18": sub.over18,
        "last_crawled_at": sub.last_crawled_at.isoformat() if sub.last_crawled_at else None,
        "profile": {
            "promotion_tolerance": profile.promotion_tolerance if profile else 0.5,
            "technical_depth": profile.technical_depth if profile else 0.5,
            "reply_style": profile.reply_style if profile else "casual_value",
            "self_promotion_risk": profile.self_promotion_risk if profile else 0.6,
            "common_topics": profile.common_topics if profile else [],
            "notes": profile.notes if profile else None,
        } if profile else None,
    }


@router.get("")
def list_subreddits(db: Session = Depends(get_db)):
    """List all tracked subreddits with community intelligence profiles."""
    sub_repo = SubredditRepository(db)
    subs = sub_repo.get_all()
    return [serialize_subreddit(s) for s in subs]


@router.post("")
def add_subreddit(req: SubredditCreate, db: Session = Depends(get_db)):
    """Add a new subreddit to track."""
    sub_repo = SubredditRepository(db)
    sub = sub_repo.upsert_subreddit(name=req.name)
    return serialize_subreddit(sub)


@router.patch("/{subreddit_id}/profile")
def update_profile(subreddit_id: int, req: SubredditProfileUpdate, db: Session = Depends(get_db)):
    """Update community sensitivity and profile for a subreddit."""
    sub_repo = SubredditRepository(db)
    profile = sub_repo.update_profile(
        subreddit_id=subreddit_id,
        promotion_tolerance=req.promotion_tolerance,
        technical_depth=req.technical_depth,
        reply_style=req.reply_style,
        common_topics=req.common_topics,
        notes=req.notes,
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Subreddit profile not found")
    return {"success": True, "message": "Profile updated"}
