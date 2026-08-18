"""
SaaS Trends & Market Intelligence Router (PulsePeek Feature Set).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from src.database.session import get_db
from src.intelligence.saas_trends import SaaSTrendsService
from src.reddit import RedditClient, RedditSearchService

router = APIRouter(prefix="/trends", tags=["Trends & SaaS Intelligence"])


@router.get("/leaderboard")
def get_saas_leaderboard(limit: int = Query(15, ge=1, le=50), db: Session = Depends(get_db)):
    """Get real-time SaaS product leaderboard and Reddit sentiment (PulsePeek feature)."""
    service = SaaSTrendsService(db)
    items = service.get_saas_leaderboard(limit=limit)
    return {
        "count": len(items),
        "leaderboard": items,
    }


@router.get("/market-gaps")
def get_market_gaps(limit: int = Query(10, ge=1, le=30), db: Session = Depends(get_db)):
    """Get top market gaps, unsolved user requests, and software demands."""
    service = SaaSTrendsService(db)
    gaps = service.get_market_gaps(limit=limit)
    return {
        "count": len(gaps),
        "gaps": gaps,
    }


@router.get("/inspect/{product_name}")
async def inspect_product(product_name: str, subreddit: str = "all"):
    """Live scan Reddit for sentiment and discussions about any specific SaaS product."""
    client = RedditClient()
    search_service = RedditSearchService(client)
    try:
        results = await search_service.search(
            query=f"{product_name} (review OR alternative OR experience OR issue OR love)",
            subreddit=subreddit,
            limit=10,
        )
        return {
            "product": product_name,
            "count": len(results),
            "discussions": [
                {
                    "title": r.title,
                    "subreddit": r.subreddit,
                    "score": r.score,
                    "comments": r.num_comments,
                    "permalink": r.permalink,
                    "posted_at": r.posted_at.isoformat() if r.posted_at else None,
                }
                for r in results
            ],
        }
    finally:
        await client.close()
