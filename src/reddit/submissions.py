"""
Reddit Submission Fetcher.
Retrieves recent submissions from subreddits using OAuth or Atom/RSS fallback.
"""

import logging
from typing import List, Optional
from .client import RedditClient
from .normalizer import normalize_submission
from .models import NormalizedSubmission

logger = logging.getLogger(__name__)


class SubmissionFetcher:
    def __init__(self, client: RedditClient):
        self.client = client

    async def fetch_subreddit_new(
        self,
        subreddit: str = "all",
        limit: int = 25,
    ) -> List[NormalizedSubmission]:
        """Fetch newest submissions for a subreddit."""
        sub = subreddit.replace("r/", "").strip()

        # 1. If OAuth credentials are active, use OAuth JSON
        if self.client.auth_manager.has_credentials:
            path = f"/r/{sub}/new"
            params = {"limit": min(limit, 100)}
            data = await self.client.request(path, params=params)
            if data and "data" in data and "children" in data["data"]:
                submissions = []
                for child in data["data"]["children"]:
                    if child.get("kind") == "t3" and "data" in child:
                        norm = normalize_submission(child["data"])
                        submissions.append(norm)
                if submissions:
                    return submissions

        # 2. In unauthenticated / public mode, directly fetch Reddit Atom/RSS feed
        rss_url = f"https://www.reddit.com/r/{sub}/new.rss?limit={min(limit, 50)}"
        return await self.client.fetch_rss_feed(rss_url)

    async def fetch_submission_by_id(
        self,
        subreddit: str,
        reddit_id: str,
    ) -> Optional[NormalizedSubmission]:
        """Fetch full details for a single submission."""
        sub = subreddit.replace("r/", "").strip()
        if self.client.auth_manager.has_credentials:
            path = f"/r/{sub}/comments/{reddit_id}"
            data = await self.client.request(path)
            if isinstance(data, list) and len(data) > 0:
                post_block = data[0]
                if "data" in post_block and "children" in post_block["data"]:
                    children = post_block["data"]["children"]
                    if children:
                        return normalize_submission(children[0]["data"])

        return None
