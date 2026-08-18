"""
Async Reddit API Client.
Seamlessly routes through OAuth (oauth.reddit.com), Public JSON, and Reddit RSS/Atom feeds.
"""

import asyncio
import logging
import re
import html
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional, List, Tuple
import httpx

from src.config import settings
from .auth import RedditAuthManager
from .rate_limits import AsyncRateLimiter
from .models import NormalizedSubmission
from .normalizer import normalize_submission

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
]


class RedditClient:
    def __init__(self):
        self.auth_manager = RedditAuthManager()
        self.rate_limiter = AsyncRateLimiter(requests_per_minute=settings.reddit.rate_limit_per_minute)
        self._client: Optional[httpx.AsyncClient] = None
        self._ua_index = 0

    def _get_ua(self) -> str:
        ua = USER_AGENTS[self._ua_index % len(USER_AGENTS)]
        self._ua_index += 1
        return ua

    async def get_http_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=15.0,
                headers={"User-Agent": self._get_ua()},
                follow_redirects=True,
            )
        return self._client

    async def request(self, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Make an authenticated or public rate-limited Reddit GET request."""
        if self.auth_manager.has_credentials:
            await self.rate_limiter.acquire()
            http_client = await self.get_http_client()
            token = await self.auth_manager.get_token(http_client)
            if token:
                url = f"https://oauth.reddit.com{path}"
                headers = {
                    "Authorization": f"Bearer {token}",
                    "User-Agent": settings.reddit.user_agent,
                }
                try:
                    resp = await http_client.get(url, params=params, headers=headers)
                    if resp.status_code == 200:
                        return resp.json()
                except Exception as e:
                    logger.warning(f"OAuth request to {url} failed: {e}")
        return None

    def _sync_fetch_rss(self, url: str) -> str:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self._get_ua(),
                "Accept": "application/atom+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8", errors="ignore")

    async def fetch_rss_feed(self, url: str) -> List[NormalizedSubmission]:
        """Fetch and parse Reddit Atom/RSS feed into NormalizedSubmission objects."""
        await self.rate_limiter.acquire()
        for attempt in range(2):
            try:
                xml_text = await asyncio.to_thread(self._sync_fetch_rss, url)
                if xml_text:
                    return self._parse_atom_xml(xml_text)
            except Exception as e:
                logger.debug(f"RSS fetch error for {url}: {e}")
                if "429" in str(e):
                    await asyncio.sleep(2.0)
                else:
                    await asyncio.sleep(1.0)
        return []

    def _parse_atom_xml(self, xml_text: str) -> List[NormalizedSubmission]:
        """Robust regex-based Atom/RSS XML parser for Reddit posts."""
        entries = re.findall(r"<entry>(.*?)</entry>", xml_text, re.DOTALL)
        results = []

        for e in entries:
            try:
                title_m = re.search(r"<title>(.*?)</title>", e)
                title = html.unescape(title_m.group(1)) if title_m else "Untitled"

                link_m = re.search(r'<link href="(.*?)"', e)
                link = link_m.group(1) if link_m else ""

                author_m = re.search(r"<name>(.*?)</name>", e)
                author = author_m.group(1).replace("/u/", "").strip() if author_m else "anonymous"

                sub_m = re.search(r"/r/([A-Za-z0-9_]+)/", link)
                subreddit = sub_m.group(1).lower() if sub_m else "all"

                id_m = re.search(r"/comments/([a-z0-9]+)/", link)
                reddit_id = id_m.group(1) if id_m else ""

                content_m = re.search(r'<content type="html">(.*?)</content>', e, re.DOTALL)
                raw_html = html.unescape(content_m.group(1)) if content_m else ""
                clean_body = re.sub(r"<[^>]+>", " ", raw_html).strip()
                clean_body = re.sub(r"\s+", " ", clean_body)

                # Filter out standard reddit footer links in RSS body
                clean_body = re.sub(r"submitted by.*?\[link\].*?\[comments\]", "", clean_body).strip()

                if reddit_id and title:
                    norm = NormalizedSubmission(
                        reddit_id=reddit_id,
                        subreddit=subreddit,
                        title=title,
                        body=clean_body,
                        author=author,
                        url=link,
                        permalink=link,
                        score=1,
                        num_comments=0,
                        upvote_ratio=1.0,
                        post_flair=None,
                        post_type="text",
                        thumbnail_url=None,
                        awards_count=0,
                    )
                    results.append(norm)
            except Exception as parse_err:
                logger.debug(f"Error parsing RSS entry: {parse_err}")

        return results

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
