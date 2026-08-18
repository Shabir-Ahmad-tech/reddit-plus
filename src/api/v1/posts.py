"""
Reddit Posts & Live Search Router.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any

from src.database.session import get_db
from src.database.repositories.post_repository import PostRepository
from src.database.repositories.comment_repository import CommentRepository
from src.api.schemas.models import LiveSearchRequest
from src.reddit import RedditClient, RedditSearchService

router = APIRouter(prefix="/posts", tags=["Posts"])


@router.get("")
def list_posts(
    subreddit: Optional[str] = None,
    query: Optional[str] = None,
    hours: Optional[int] = None,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List stored Reddit posts with pagination and filters."""
    post_repo = PostRepository(db)
    posts, total = post_repo.get_recent(
        subreddit=subreddit,
        query=query,
        hours=hours,
        limit=limit,
        offset=offset,
    )

    items = []
    for p in posts:
        analysis = p.analysis
        items.append({
            "id": p.id,
            "reddit_id": p.reddit_id,
            "subreddit": p.subreddit,
            "title": p.title,
            "body": p.body,
            "author": p.author,
            "score": p.score,
            "num_comments": p.num_comments,
            "upvote_ratio": p.upvote_ratio,
            "post_flair": p.post_flair,
            "post_type": p.post_type,
            "url": p.url,
            "permalink": p.permalink,
            "posted_at": p.posted_at.isoformat() if p.posted_at else None,
            "intent_tag": analysis.intent_tag if analysis else None,
            "intent_confidence": analysis.intent_confidence if analysis else None,
            "urgency": analysis.urgency if analysis else None,
            "sentiment": analysis.sentiment if analysis else None,
            "buy_signal_strength": analysis.buy_signal_strength if analysis else None,
        })

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{post_id}")
def get_post_detail(post_id: int, db: Session = Depends(get_db)):
    """Get single Reddit post with comments and analysis."""
    post_repo = PostRepository(db)
    comment_repo = CommentRepository(db)

    post = post_repo.get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    comments = comment_repo.get_by_post(post.id, limit=20)

    return {
        "id": post.id,
        "reddit_id": post.reddit_id,
        "subreddit": post.subreddit,
        "title": post.title,
        "body": post.body,
        "author": post.author,
        "score": post.score,
        "num_comments": post.num_comments,
        "upvote_ratio": post.upvote_ratio,
        "post_flair": post.post_flair,
        "post_type": post.post_type,
        "url": post.url,
        "permalink": post.permalink,
        "posted_at": post.posted_at.isoformat() if post.posted_at else None,
        "comments": [
            {
                "id": c.id,
                "author": c.author,
                "score": c.score,
                "body": c.body,
                "posted_at": c.posted_at.isoformat() if c.posted_at else None,
            }
            for c in comments
        ],
        "analysis": {
            "summary": post.analysis.summary if post.analysis else None,
            "what_it_means": post.analysis.what_it_means if post.analysis else None,
            "what_it_requires": post.analysis.what_it_requires if post.analysis else None,
            "urgency": post.analysis.urgency if post.analysis else None,
            "sentiment": post.analysis.sentiment if post.analysis else None,
            "intent_tag": post.analysis.intent_tag if post.analysis else None,
        } if post.analysis else None,
    }


@router.post("/live-search")
async def live_search_reddit(req: LiveSearchRequest):
    """Execute on-the-fly live search against Reddit."""
    client = RedditClient()
    search_service = RedditSearchService(client)
    try:
        results = await search_service.search(
            query=req.query,
            subreddit=req.subreddit,
            sort=req.sort,
            time_filter=req.time_filter,
            limit=req.limit,
        )
        return {
            "query": req.query,
            "subreddit": req.subreddit,
            "count": len(results),
            "items": [
                {
                    "reddit_id": r.reddit_id,
                    "subreddit": r.subreddit,
                    "title": r.title,
                    "body": r.body[:300] if r.body else "",
                    "author": r.author,
                    "score": r.score,
                    "num_comments": r.num_comments,
                    "upvote_ratio": r.upvote_ratio,
                    "post_flair": r.post_flair,
                    "post_type": r.post_type,
                    "permalink": r.permalink,
                    "posted_at": r.posted_at.isoformat() if r.posted_at else None,
                }
                for r in results
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Live search failed: {e}")
