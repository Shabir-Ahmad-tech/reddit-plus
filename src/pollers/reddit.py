import logging
import time
import random
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
import httpx

from src.config import settings
from src.database import upsert_mention, get_session

logger = logging.getLogger(__name__)

# Reddit-style post type detection
_LINK_DOMAINS_SKIP = {"self", "i.redd.it", "v.redd.it", "gallery"}


def _detect_post_type(post_data: dict) -> str:
    """Detect post type from Reddit JSON data."""
    is_self = post_data.get("is_self", False)
    is_video = post_data.get("is_video", False)
    is_gallery = post_data.get("is_gallery", False)
    url = post_data.get("url", "")
    if is_video:
        return "video"
    if is_gallery:
        return "gallery"
    if is_self:
        return "text"
    if url and any(ext in url.lower() for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]):
        return "image"
    return "link"


def _safe_thumbnail(url: Optional[str]) -> Optional[str]:
    """Return thumbnail URL if it looks like a real image URL."""
    if not url:
        return None
    if url.startswith("http") and not url in ("self", "default", "nsfw", "spoiler"):
        return url
    return None


class RedditPoller:
    def __init__(self):
        self.client_id = settings.reddit.client_id
        self.client_secret = settings.reddit.client_secret
        self.user_agent = settings.reddit.user_agent or "ParseStream-Reddit/2.0"
        self.subreddits = settings.reddit.subreddits or ["all"]
        self.max_per_poll = settings.app.max_mentions_per_poll
        self.http_client = httpx.AsyncClient(
            headers={"User-Agent": f"Mozilla/5.0 (compatible) {self.user_agent}"},
            timeout=20.0,
            follow_redirects=True,
        )

        self._praw_reddit = None
        if self._has_valid_credentials():
            try:
                import praw
                self._praw_reddit = praw.Reddit(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    user_agent=self.user_agent,
                )
            except Exception as e:
                logger.warning(f"Failed to initialize PRAW: {e}")

    def _has_valid_credentials(self) -> bool:
        cid = self.client_id.strip() if self.client_id else ""
        csec = self.client_secret.strip() if self.client_secret else ""
        return bool(cid and csec and not cid.startswith("${") and not csec.startswith("${"))

    def poll(self, keywords: List[str], subreddits: Optional[List[str]] = None) -> int:
        """Poll Reddit for mentions across all active subreddits using JSON API."""
        if not keywords:
            logger.warning("No keywords configured, skipping Reddit poll")
            return 0

        new_count = 0
        raw_subs = subreddits or self.subreddits or ["all"]
        target_subs = list(set([s.strip() for s in raw_subs if s and s.strip()]))

        if self._praw_reddit:
            for subreddit_name in target_subs:
                try:
                    subreddit = self._praw_reddit.subreddit(subreddit_name)
                    for keyword in keywords:
                        new_count += self._search_praw_subreddit(subreddit, keyword)
                except Exception as e:
                    logger.warning(f"PRAW failed for r/{subreddit_name}: {e}. Falling back to JSON API.")
                    for keyword in keywords:
                        new_count += self._search_json_api(subreddit_name, keyword)
        else:
            for subreddit_name in target_subs:
                for keyword in keywords:
                    new_count += self._search_json_api(subreddit_name, keyword)

        return new_count

    def _search_praw_subreddit(self, subreddit, keyword: str) -> int:
        """Search a single subreddit for a keyword via PRAW (gets full data)."""
        count = 0
        try:
            for submission in subreddit.search(
                keyword,
                sort="new",
                time_filter="week",
                limit=self.max_per_poll,
            ):
                data = {
                    "id": submission.id,
                    "title": submission.title,
                    "selftext": submission.selftext,
                    "author": str(submission.author) if submission.author else "[deleted]",
                    "subreddit": submission.subreddit.display_name,
                    "score": submission.score,
                    "permalink": submission.permalink,
                    "created_utc": submission.created_utc,
                    "num_comments": submission.num_comments,
                    "upvote_ratio": submission.upvote_ratio,
                    "link_flair_text": submission.link_flair_text,
                    "is_self": submission.is_self,
                    "is_video": submission.is_video,
                    "url": submission.url,
                    "thumbnail": submission.thumbnail,
                    "total_awards_received": submission.total_awards_received,
                }
                if self._process_submission_dict(data):
                    count += 1
        except Exception as e:
            logger.error(f"Error searching r/{subreddit.display_name} via PRAW for '{keyword}': {e}")
        return count

    def _search_json_api(self, subreddit_name: str, keyword: str) -> int:
        """Search Reddit using its public JSON API — gets real votes, comments, flair."""
        import re
        count = 0
        terms = [t.lower().strip() for t in keyword.split(",") if t.strip()] or [keyword.lower().strip()]
        sub = "all" if subreddit_name.lower() in ("all", "popular", "") else subreddit_name
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)

        headers = {"User-Agent": f"Mozilla/5.0 (compatible) {self.user_agent}"}

        # Strategy 1: Search endpoint (best keyword matching)
        try:
            search_url = f"https://www.reddit.com/r/{sub}/search.json"
            params = {
                "q": keyword,
                "sort": "new",
                "t": "week",
                "limit": min(self.max_per_poll, 25),
                "restrict_sr": "true" if sub != "all" else "false",
            }
            with httpx.Client(headers=headers, timeout=12.0, follow_redirects=True) as client:
                resp = client.get(search_url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    posts = data.get("data", {}).get("children", [])
                    for post in posts:
                        pd = post.get("data", {})
                        # Recency check
                        created_utc = pd.get("created_utc", 0)
                        post_dt = datetime.fromtimestamp(created_utc, tz=timezone.utc)
                        if post_dt < cutoff:
                            continue
                        if self._process_submission_dict(pd):
                            count += 1
                elif resp.status_code == 429:
                    logger.warning("Reddit rate limited. Waiting 5s...")
                    time.sleep(5)
        except Exception as e:
            logger.debug(f"JSON search error for r/{sub} keyword '{keyword}': {e}")

        # Strategy 2: /new.json for RSS-supplemented posts
        if count == 0:
            try:
                new_url = f"https://www.reddit.com/r/{sub}/new.json"
                with httpx.Client(headers=headers, timeout=10.0, follow_redirects=True) as client:
                    resp = client.get(new_url, params={"limit": 25})
                    if resp.status_code == 200:
                        data = resp.json()
                        posts = data.get("data", {}).get("children", [])
                        for post in posts:
                            pd = post.get("data", {})
                            created_utc = pd.get("created_utc", 0)
                            post_dt = datetime.fromtimestamp(created_utc, tz=timezone.utc)
                            if post_dt < cutoff:
                                continue
                            # Keyword filter
                            title = pd.get("title", "").lower()
                            selftext = pd.get("selftext", "").lower()
                            full_text = f"{title} {selftext}"
                            if any(term in full_text for term in terms):
                                if self._process_submission_dict(pd):
                                    count += 1
            except Exception as e:
                logger.debug(f"/new.json fallback error for r/{sub}: {e}")

        return count

    async def search_live(self, keyword: str, subreddit: str = "all", limit: int = 15) -> List[Dict[str, Any]]:
        """Live search using Reddit JSON API for UI preview — returns rich post data."""
        results = []
        terms = [t.lower().strip() for t in keyword.split(",") if t.strip()] or [keyword.lower().strip()]
        sub = "all" if not subreddit or subreddit.lower() in ("all", "") else subreddit
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)

        # Primary: search endpoint
        try:
            search_url = f"https://www.reddit.com/r/{sub}/search.json"
            params = {
                "q": keyword,
                "sort": "new",
                "t": "week",
                "limit": min(limit * 2, 50),
                "restrict_sr": "true" if sub != "all" else "false",
            }
            resp = await self.http_client.get(search_url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                posts = data.get("data", {}).get("children", [])
                for post in posts:
                    pd = post.get("data", {})
                    created_utc = pd.get("created_utc", 0)
                    post_dt = datetime.fromtimestamp(created_utc, tz=timezone.utc)
                    if post_dt < cutoff:
                        continue

                    title = pd.get("title", "")
                    selftext = pd.get("selftext", "")
                    author = pd.get("author", "[deleted]")
                    post_id = pd.get("id", "")
                    permalink = pd.get("permalink", "")
                    url = f"https://reddit.com{permalink}" if permalink.startswith("/") else permalink

                    results.append({
                        "source": "reddit",
                        "source_id": post_id,
                        "title": title,
                        "content": f"{title}\n\n{selftext}".strip(),
                        "author": author,
                        "subreddit": pd.get("subreddit", sub),
                        "url": url,
                        "score": pd.get("score", 0),
                        "num_comments": pd.get("num_comments", 0),
                        "upvote_ratio": pd.get("upvote_ratio", 0.0),
                        "post_flair": pd.get("link_flair_text"),
                        "post_type": _detect_post_type(pd),
                        "thumbnail_url": _safe_thumbnail(pd.get("thumbnail")),
                        "awards_count": pd.get("total_awards_received", 0),
                        "posted_at": post_dt.isoformat(),
                    })
                    if len(results) >= limit:
                        break
        except Exception as e:
            logger.debug(f"Live JSON search error for r/{sub}: {e}")

        # Fallback: /new.json with keyword filter
        if not results:
            try:
                resp = await self.http_client.get(
                    f"https://www.reddit.com/r/{sub}/new.json",
                    params={"limit": 50}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    posts = data.get("data", {}).get("children", [])
                    for post in posts:
                        pd = post.get("data", {})
                        created_utc = pd.get("created_utc", 0)
                        post_dt = datetime.fromtimestamp(created_utc, tz=timezone.utc)
                        if post_dt < cutoff:
                            continue
                        title = pd.get("title", "")
                        selftext = pd.get("selftext", "")
                        if not any(t in f"{title} {selftext}".lower() for t in terms):
                            continue
                        permalink = pd.get("permalink", "")
                        url = f"https://reddit.com{permalink}" if permalink.startswith("/") else permalink
                        results.append({
                            "source": "reddit",
                            "source_id": pd.get("id", ""),
                            "title": title,
                            "content": f"{title}\n\n{selftext}".strip(),
                            "author": pd.get("author", "[deleted]"),
                            "subreddit": pd.get("subreddit", sub),
                            "url": url,
                            "score": pd.get("score", 0),
                            "num_comments": pd.get("num_comments", 0),
                            "upvote_ratio": pd.get("upvote_ratio", 0.0),
                            "post_flair": pd.get("link_flair_text"),
                            "post_type": _detect_post_type(pd),
                            "thumbnail_url": _safe_thumbnail(pd.get("thumbnail")),
                            "awards_count": pd.get("total_awards_received", 0),
                            "posted_at": post_dt.isoformat(),
                        })
                        if len(results) >= limit:
                            break
            except Exception as e:
                logger.debug(f"Live /new.json fallback error for r/{sub}: {e}")

        return results

    def _process_submission_dict(self, data: dict) -> bool:
        """Process Reddit submission dict into a mention with all rich fields."""
        try:
            submission_id = data.get("id")
            if not submission_id:
                return False

            title = data.get("title", "")
            selftext = data.get("selftext", "") or ""
            # Skip removed/deleted posts
            if selftext in ("[removed]", "[deleted]"):
                selftext = ""
            content = f"{title}\n\n{selftext}".strip() if selftext else title

            if not content.strip():
                return False

            created_utc = data.get("created_utc") or datetime.now().timestamp()
            post_dt = datetime.fromtimestamp(created_utc, tz=timezone.utc)

            # Reject posts older than 14 days
            if (datetime.now(timezone.utc) - post_dt).days > 14:
                return False

            permalink = data.get("permalink", "")
            url_str = data.get("url", "")
            if permalink and permalink.startswith("/"):
                url = f"https://reddit.com{permalink}"
            elif url_str.startswith("http"):
                url = url_str
            else:
                url = f"https://reddit.com{permalink}"

            author = data.get("author", "[deleted]") or "[deleted]"
            subreddit = data.get("subreddit", "")
            score = data.get("score", 0) or 0
            num_comments = data.get("num_comments", 0) or 0
            upvote_ratio = float(data.get("upvote_ratio", 0.0) or 0.0)
            post_flair = data.get("link_flair_text") or data.get("post_flair")
            post_type = _detect_post_type(data)
            thumbnail_url = _safe_thumbnail(data.get("thumbnail"))
            awards_count = int(data.get("total_awards_received", 0) or 0)

            with get_session() as session:
                mention, is_new = upsert_mention(
                    session=session,
                    source="reddit",
                    source_id=str(submission_id),
                    url=url,
                    title=title,
                    content=content,
                    author=author,
                    subreddit=subreddit,
                    score=score,
                    posted_at=post_dt,
                    num_comments=num_comments,
                    upvote_ratio=upvote_ratio,
                    post_flair=post_flair,
                    post_type=post_type,
                    thumbnail_url=thumbnail_url,
                    awards_count=awards_count,
                )
                return is_new
        except Exception as e:
            logger.error(f"Error processing Reddit submission {data.get('id')}: {e}")
            return False

    def test_connection(self) -> bool:
        """Test Reddit connection."""
        if self._has_valid_credentials() and self._praw_reddit:
            try:
                self._praw_reddit.subreddit("test").search("test", limit=1)
                logger.info("Reddit PRAW API connection OK")
                return True
            except Exception as e:
                logger.warning(f"Reddit PRAW test failed: {e}")

        try:
            with httpx.Client(headers={"User-Agent": self.user_agent}, timeout=5.0) as client:
                r = client.get("https://www.reddit.com/r/popular.json?limit=1")
                if r.status_code == 200:
                    logger.info("Reddit Public JSON connection OK")
                    return True
        except Exception as e:
            logger.error(f"Reddit public connection test failed: {e}")
        return False

    async def close(self):
        await self.http_client.aclose()