"""
Async Reddit API Client.
Seamlessly routes through OAuth (oauth.reddit.com) or Public JSON (www.reddit.com) endpoints.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
import httpx

from src.config import settings
from .auth import RedditAuthManager
from .rate_limits import AsyncRateLimiter

logger = logging.getLogger(__name__)


class RedditClient:
    def __init__(self):
        self.auth_manager = RedditAuthManager()
        self.rate_limiter = AsyncRateLimiter(requests_per_minute=settings.reddit.rate_limit_per_minute)
        self._client: Optional[httpx.AsyncClient] = None

    async def get_http_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=25.0,
                headers={"User-Agent": settings.reddit.user_agent},
                follow_redirects=True,
            )
        return self._client

    async def request(self, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Make an authenticated or public rate-limited Reddit GET request."""
        await self.rate_limiter.acquire()
        http_client = await self.get_http_client()

        token = await self.auth_manager.get_token(http_client)

        if token:
            url = f"https://oauth.reddit.com{path}"
            headers = {
                "Authorization": f"Bearer {token}",
                "User-Agent": settings.reddit.user_agent,
            }
        else:
            # Fallback to public JSON endpoint
            clean_path = path.rstrip("/")
            if not clean_path.endswith(".json"):
                clean_path = f"{clean_path}.json"
            url = f"https://www.reddit.com{clean_path}"
            headers = {
                "User-Agent": settings.reddit.user_agent,
                "Accept": "application/json",
            }

        for attempt in range(3):
            try:
                resp = await http_client.get(url, params=params, headers=headers)

                if resp.status_code == 429:
                    wait_time = 2.0 ** attempt + 1.0
                    logger.warning(f"Reddit 429 rate-limited. Backing off for {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue

                if resp.status_code == 404:
                    logger.debug(f"Reddit endpoint {url} returned 404")
                    return None

                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                logger.warning(f"Reddit HTTP error on {url} (status {e.response.status_code}): {e}")
                if attempt == 2:
                    return None
            except Exception as e:
                logger.warning(f"Reddit request failed on {url}: {e}")
                if attempt == 2:
                    return None
                await asyncio.sleep(1.0)

        return None

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
