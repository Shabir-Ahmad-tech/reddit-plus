"""
Submissions Ingestion Service.
Fetches new posts and post details with normalization.
"""

import logging
from typing import List, Optional
from datetime import datetime

from .client import RedditClient
from .normalizer import normalize_submission
from .models import NormalizedSubmission

logger = logging.getLogger(__name__)


class SubmissionFetcher:
    def __init__(self, client: RedditClient):
        self.client = client

    async def fetch_subreddit_new(
        self,
        subreddit: str,
        limit: int = 50,
        after: Optional[str] = None,
    ) -> List[NormalizedSubmission]:
        """Fetch newest posts from a subreddit."""
        sub = subreddit.replace("r/", "").strip()
        path = f"/r/{sub}/new"
        params = {"limit": min(limit, 100)}
        if after:
            params["after"] = after

        data = await self.client.request(path, params=params)
        if not data or "data" not in data or "children" not in data["data"]:
            return []

        results = []
        for child in data["data"]["children"]:
            if child.get("kind") == "t3" and "data" in child:
                norm = normalize_submission(child["data"])
                results.append(norm)

        return results

    async def fetch_submission_by_id(self, reddit_id: str) -> Optional[NormalizedSubmission]:
        """Fetch full details for a single Reddit submission."""
        clean_id = reddit_id.replace("t3_", "")
        path = f"/by_id/t3_{clean_id}"
        data = await self.client.request(path)
        if not data or "data" not in data or "children" not in data["data"]:
            return None

        children = data["data"]["children"]
        if children:
            return normalize_submission(children[0]["data"])
        return None
