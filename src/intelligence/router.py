"""
AI Model Router.
Intelligently routes AI tasks to appropriate models with automatic failover and rate-limit rotation.
"""

import os
import re
import json
import logging
from typing import Optional, Dict, Any, List
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings

logger = logging.getLogger(__name__)


class AIRouter:
    """Unified AI Router supporting OpenCode Zen, Ollama, and multi-model rotation."""

    FREE_ZEN_MODELS = [
        "deepseek-v4-flash-free",
        "nemotron-3.5-lightning-free",
        "mimo-v2.5-free",
        "hy3-free",
        "gemini-3.5-flash-lite",
    ]

    def __init__(self):
        self._http_client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=60.0)
        return self._http_client

    @property
    def provider(self) -> str:
        return settings.llm.provider

    @property
    def active_model(self) -> str:
        if self.provider == "ollama":
            return settings.llm.ollama.model
        return settings.llm.opencode_zen.model or "deepseek-v4-flash-free"

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        task_type: str = "general",  # classification, analysis, reply, critic, expansion
        temperature: float = 0.3,
        max_tokens: int = 800,
        format_json: bool = False,
    ) -> str:
        """Generate text completion from primary AI backend with automatic fallback."""
        if self.provider in ("opencode_zen", "auto"):
            api_key = settings.llm.opencode_zen.api_key
            if api_key:
                try:
                    return await self._generate_zen(
                        prompt=prompt,
                        system=system,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        format_json=format_json,
                    )
                except Exception as e:
                    logger.warning(f"OpenCode Zen error ({e}). Attempting Ollama fallback...")

        # Fallback to Ollama
        try:
            return await self._generate_ollama(
                prompt=prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
                format_json=format_json,
            )
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise

    async def _generate_zen(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 800,
        format_json: bool = False,
    ) -> str:
        client = await self.get_client()
        base_url = settings.llm.opencode_zen.base_url.rstrip("/")
        api_key = settings.llm.opencode_zen.api_key

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        elif format_json:
            messages.append({"role": "system", "content": "You are a helpful AI assistant. Always output valid JSON only."})

        messages.append({"role": "user", "content": prompt})

        # Try active model then fallbacks if rate limited
        models_to_try = [self.active_model]
        for m in self.FREE_ZEN_MODELS:
            if m not in models_to_try:
                models_to_try.append(m)

        last_err = None
        for model in models_to_try:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            try:
                resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
                if resp.status_code == 429:
                    logger.warning(f"Model '{model}' rate-limited (429), rotating to next model...")
                    continue

                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    return content.strip()
            except Exception as e:
                logger.warning(f"Zen request error on model {model}: {e}")
                last_err = e
                continue

        if last_err:
            raise last_err
        return ""

    async def _generate_ollama(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 800,
        format_json: bool = False,
    ) -> str:
        client = await self.get_client()
        host = settings.llm.ollama.host.rstrip("/")
        payload = {
            "model": settings.llm.ollama.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system
        if format_json:
            payload["format"] = "json"

        resp = await client.post(f"{host}/api/generate", json=payload, timeout=settings.llm.ollama.timeout_seconds)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()

    async def close(self):
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()


# Singleton
_ai_router: Optional[AIRouter] = None


def get_ai_router() -> AIRouter:
    global _ai_router
    if _ai_router is None:
        _ai_router = AIRouter()
    return _ai_router
