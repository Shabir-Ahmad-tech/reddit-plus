"""
Reddit OAuth Token Manager.
"""

import time
import base64
import logging
from typing import Optional, Tuple
import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class RedditAuthManager:
    """Manages Reddit OAuth2 application-only access tokens."""

    def __init__(self):
        self.access_token: Optional[str] = None
        self.token_expiry: float = 0.0
        self.has_credentials = bool(settings.reddit.client_id and settings.reddit.client_secret)

    async def get_token(self, client: httpx.AsyncClient) -> Optional[str]:
        if not self.has_credentials:
            return None

        now = time.time()
        if self.access_token and now < self.token_expiry - 60:
            return self.access_token

        # Request new app-only token
        auth_header = base64.b64encode(
            f"{settings.reddit.client_id}:{settings.reddit.client_secret}".encode()
        ).decode()

        headers = {
            "Authorization": f"Basic {auth_header}",
            "User-Agent": settings.reddit.user_agent,
        }
        data = {
            "grant_type": "client_credentials",
        }

        try:
            resp = await client.post(
                "https://www.reddit.com/api/v1/access_token",
                headers=headers,
                data=data,
                timeout=15.0,
            )
            resp.raise_for_status()
            token_data = resp.json()
            self.access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)
            self.token_expiry = now + expires_in
            logger.info("Acquired fresh Reddit OAuth token")
            return self.access_token
        except Exception as e:
            logger.warning(f"Reddit OAuth token acquisition failed: {e}. Falling back to public JSON.")
            return None
