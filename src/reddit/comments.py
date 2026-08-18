"""
Comments Ingestion Service.
Fetches top comments and comment trees for Reddit submissions.
"""

import logging
from typing import List, Optional
from .client import RedditClient
from .normalizer import normalize_comment
from .models import NormalizedComment

logger = logging.getLogger(__name__)


class CommentFetcher:
    def __init__(self, client: RedditClient):
        self.client = client

    async def fetch_post_comments(
        self,
        subreddit: str,
        post_reddit_id: str,
        limit: int = 15,
        sort: str = "top",
    ) -> List[NormalizedComment]:
        """Fetch top comments for a Reddit post."""
        clean_sub = subreddit.replace("r/", "").strip()
        clean_id = post_reddit_id.replace("t3_", "")
        path = f"/r/{clean_sub}/comments/{clean_id}"
        params = {"limit": limit, "sort": sort, "depth": 2}

        data = await self.client.request(path, params=params)
        if not data or not isinstance(data, list) or len(data) < 2:
            return []

        comment_listing = data[1]
        if "data" not in comment_listing or "children" not in comment_listing["data"]:
            return []

        results = []
        for child in comment_listing["data"]["children"]:
            if child.get("kind") == "t1" and "data" in child:
                cdata = child["data"]
                # Skip deleted or empty comments
                if cdata.get("body") and cdata["body"] != "[deleted]":
                    norm = normalize_comment(cdata, post_reddit_id=clean_id)
                    results.append(norm)

        return results
