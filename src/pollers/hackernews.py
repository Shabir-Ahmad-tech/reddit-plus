import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import httpx

from src.config import settings
from src.database import upsert_mention, get_session

logger = logging.getLogger(__name__)


class HackerNewsPoller:
    def __init__(self):
        self.base_url = settings.hackernews.base_url.rstrip("/")
        self.algolia_url = "https://hn.algolia.com/api/v1"
        self.client = httpx.AsyncClient(timeout=20.0)
        self.max_per_poll = settings.app.max_mentions_per_poll

    async def poll(self, keywords: List[str]) -> int:
        """Poll Hacker News for mentions matching keywords. Returns count of new mentions."""
        if not settings.hackernews.enabled:
            return 0

        if not keywords:
            logger.warning("No keywords configured, skipping HN poll")
            return 0

        new_count = 0

        for keyword in keywords:
            try:
                # Prefer Algolia search for fast, accurate keyword matching
                hits = await self._search_algolia(keyword)
                if hits:
                    for hit in hits[:self.max_per_poll]:
                        if self._process_algolia_hit(hit):
                            new_count += 1
                else:
                    # Fallback to Firebase recent stories
                    new_count += await self._poll_firebase([keyword])
            except Exception as e:
                logger.error(f"Error polling Hacker News for '{keyword}': {e}")

        return new_count

    async def search_live(self, keyword: str, limit: int = 15) -> List[Dict[str, Any]]:
        """Search live HN items for UI preview."""
        try:
            hits = await self._search_algolia(keyword, limit=limit)
            results = []
            for hit in hits:
                title = hit.get("title") or hit.get("story_title") or "[Comment]"
                content = hit.get("comment_text") or hit.get("story_text") or title
                results.append({
                    "source": "hackernews",
                    "source_id": str(hit.get("objectID", "")),
                    "title": title,
                    "content": content,
                    "author": hit.get("author", "unknown"),
                    "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    "score": hit.get("points") or 0,
                    "posted_at": hit.get("created_at", ""),
                })
            return results
        except Exception as e:
            logger.error(f"Live search HN failed for '{keyword}': {e}")
            return []

    async def _search_algolia(self, keyword: str, limit: int = 25) -> List[dict]:
        """Search HN Algolia API by date for keyword."""
        try:
            url = f"{self.algolia_url}/search_by_date"
            params = {
                "query": keyword,
                "tags": "(story,comment)",
                "hitsPerPage": limit,
            }
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("hits", [])
        except Exception as e:
            logger.debug(f"HN Algolia search failed for '{keyword}': {e}")
            return []

    def _process_algolia_hit(self, hit: dict) -> bool:
        """Process an Algolia hit and store as mention. Returns True if newly added."""
        try:
            object_id = str(hit.get("objectID"))
            if not object_id:
                return False

            title = hit.get("title") or hit.get("story_title") or ""
            text = hit.get("comment_text") or hit.get("story_text") or ""
            content = f"{title}\n\n{text}".strip() if title and text else (text or title)

            if not content:
                return False

            # Parse timestamp
            created_at_str = hit.get("created_at")
            if created_at_str:
                try:
                    posted_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                except Exception:
                    posted_at = datetime.now(timezone.utc)
            else:
                posted_at = datetime.now(timezone.utc)

            url = hit.get("url")
            if not url or "http" not in url:
                url = f"https://news.ycombinator.com/item?id={object_id}"

            with get_session() as session:
                mention, is_new = upsert_mention(
                    session=session,
                    source="hackernews",
                    source_id=object_id,
                    url=url,
                    title=title or "HN Discussion",
                    content=content,
                    author=hit.get("author", "unknown"),
                    subreddit=None,
                    score=hit.get("points") or 0,
                    posted_at=posted_at,
                )
                return is_new

        except Exception as e:
            logger.error(f"Error processing Algolia hit: {e}")
            return False

    async def _poll_firebase(self, keywords: List[str]) -> int:
        """Fallback poller using official Firebase endpoint."""
        count = 0
        try:
            response = await self.client.get(f"{self.base_url}/newstories.json")
            response.raise_for_status()
            story_ids = response.json() or []

            for story_id in story_ids[:20]:
                resp = await self.client.get(f"{self.base_url}/item/{story_id}.json")
                if resp.status_code == 200:
                    story = resp.json()
                    if story and self._matches_keywords(story, keywords):
                        if self._process_story(story):
                            count += 1
        except Exception as e:
            logger.error(f"HN Firebase polling error: {e}")
        return count

    def _matches_keywords(self, story: dict, keywords: List[str]) -> bool:
        text = f"{story.get('title', '')} {story.get('text', '')}".lower()
        return any(k.lower() in text for k in keywords)

    def _process_story(self, story: dict) -> bool:
        try:
            if story.get("type") != "story":
                return False
            title = story.get("title", "")
            text = story.get("text", "")
            content = f"{title}\n\n{text}".strip() if text else title
            if not content:
                return False

            with get_session() as session:
                mention, is_new = upsert_mention(
                    session=session,
                    source="hackernews",
                    source_id=str(story["id"]),
                    url=story.get("url", f"https://news.ycombinator.com/item?id={story['id']}"),
                    title=title,
                    content=content,
                    author=story.get("by"),
                    subreddit=None,
                    score=story.get("score", 0),
                    posted_at=datetime.fromtimestamp(story.get("time", 0), tz=timezone.utc),
                )
                return is_new
        except Exception as e:
            logger.error(f"Error processing HN story: {e}")
            return False

    async def close(self):
        await self.client.aclose()

    async def test_connection(self) -> bool:
        """Test HN connection (Algolia and Firebase)."""
        try:
            resp = await self.client.get(f"{self.algolia_url}/search?tags=front_page&hitsPerPage=1")
            if resp.status_code == 200:
                logger.info("Hacker News Algolia connection OK")
                return True
        except Exception:
            pass

        try:
            resp = await self.client.get(f"{self.base_url}/item/8863.json")
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"HN connection test failed: {e}")
            return False