"""
Reddit Search Service.
Searches subreddits or global Reddit for keywords with sorting and recency filters.
"""

import logging
import urllib.parse
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
        """Search Reddit submissions via OAuth JSON or public RSS feed."""
        sub = subreddit.replace("r/", "").strip() if subreddit else "all"

        # 1. If OAuth credentials are active, use OAuth JSON
        if self.client.auth_manager.has_credentials:
            path = f"/r/{sub}/search"
            params = {
                "q": query,
                "sort": sort,
                "t": time_filter,
                "limit": min(limit, 100),
                "restrict_sr": "on" if (subreddit and subreddit != "all") else "off",
            }
            data = await self.client.request(path, params=params)
            if data and "data" in data and "children" in data["data"]:
                results = []
                for child in data["data"]["children"]:
                    if child.get("kind") == "t3" and "data" in child:
                        norm = normalize_submission(child["data"])
                        results.append(norm)
                if results:
                    return results

        # 2. In unauthenticated / public mode, fetch via search.rss
        encoded_q = urllib.parse.quote(query)
        restrict_sr = "on" if (subreddit and subreddit != "all") else "off"
        rss_url = f"https://www.reddit.com/r/{sub}/search.rss?q={encoded_q}&sort={sort}&restrict_sr={restrict_sr}&limit={min(limit, 50)}"

        return await self.client.fetch_rss_feed(rss_url)
