"""
Reddit Search Service.
Searches subreddits or global Reddit for keywords with sorting and recency filters.
"""

import logging
from typing import List, Optional
from .client import RedditClient
from .normalizer import normalize_submission
from .models import NormalizedSubmission

logger = logging.getLogger(__name__)


class RedditSearchService:
    def __init__(self, client: RedditClient):
        self.client = client

    async def search(
        self,
        query: str,
        subreddit: Optional[str] = None,
        sort: str = "new",  # new, relevance, top
        time_filter: str = "all",  # hour, day, week, month, year, all
        limit: int = 25,
    ) -> List[NormalizedSubmission]:
        """Search Reddit submissions."""
        sub = subreddit.replace("r/", "").strip() if subreddit else "all"
        path = f"/r/{sub}/search"
        params = {
            "q": query,
            "sort": sort,
            "t": time_filter,
            "limit": min(limit, 100),
            "restrict_sr": "on" if (subreddit and subreddit != "all") else "off",
        }

        data = await self.client.request(path, params=params)
        if not data or "data" not in data or "children" not in data["data"]:
            return []

        results = []
        for child in data["data"]["children"]:
            if child.get("kind") == "t3" and "data" in child:
                norm = normalize_submission(child["data"])
                results.append(norm)

        return results
