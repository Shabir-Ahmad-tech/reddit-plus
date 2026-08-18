import json
import logging
import os
import re
from typing import Optional, Dict, Any, List
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings

logger = logging.getLogger(__name__)


class OpenCodeZenClient:
    """Client for OpenCode AI Zen OpenAI-compatible API gateway."""
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.api_key = api_key or getattr(settings.llm.opencode_zen, "api_key", "") or os.environ.get("OPENCODE_ZEN_API_KEY", "")
        self.base_url = (base_url or getattr(settings.llm.opencode_zen, "base_url", "https://opencode.ai/zen/v1")).rstrip("/")
        self.model = model or getattr(settings.llm.opencode_zen, "model", "deepseek-v4-flash-free")
        self.timeout = timeout or getattr(settings.llm.opencode_zen, "timeout_seconds", 60)
        self.client = httpx.AsyncClient(timeout=self.timeout)

    FREE_MODEL_FALLBACKS = [
        "deepseek-v4-flash-free",
        "nemotron-3.5-lightning-free",
        "mimo-v2.5-free",
        "hy3-free",
        "nemotron-3-ultra-free",
        "laguna-s-2.1-free",
    ]

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 500,
        format_json: bool = False,
    ) -> str:
        """Generate text completion from OpenCode Zen with automatic multi-model rotation on rate limits."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        if format_json and not system:
            messages.append({"role": "system", "content": "You are a helpful AI assistant. Always respond with valid JSON only."})
        messages.append({"role": "user", "content": prompt})

        # Try selected model, followed by alternative free models if rate-limited
        models_to_try = [self.model]
        if "free" in self.model:
            for alt in self.FREE_MODEL_FALLBACKS:
                if alt not in models_to_try:
                    models_to_try.append(alt)

        last_err = None
        for candidate_model in models_to_try:
            payload = {
                "model": candidate_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            try:
                response = await self.client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                if response.status_code == 429:
                    logger.warning(f"OpenCode Zen model '{candidate_model}' rate-limited (429), rotating to next model...")
                    continue

                response.raise_for_status()
                data = response.json()
                choices = data.get("choices", [])
                if choices and len(choices) > 0:
                    msg = choices[0].get("message", {})
                    content = msg.get("content", "")
                    return content.strip()
            except Exception as e:
                logger.warning(f"OpenCode Zen error on {candidate_model}: {e}")
                last_err = e
                continue

        if last_err:
            raise last_err
        return ""

    async def list_models(self) -> List[str]:
        """List available models on OpenCode Zen."""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            response = await self.client.get(f"{self.base_url}/models", headers=headers)
            response.raise_for_status()
            data = response.json()
            return [m["id"] for m in data.get("data", [])]
        except Exception as e:
            logger.error(f"Failed to list OpenCode Zen models: {e}")
            return []

    async def health_check(self) -> bool:
        """Check if OpenCode Zen API key is valid and responsive."""
        if not self.api_key or "your_" in self.api_key:
            return False
        try:
            models = await self.list_models()
            return len(models) > 0
        except Exception:
            return False

    async def close(self):
        await self.client.aclose()


class OllamaClient:
    """Client for local Ollama server."""
    def __init__(self):
        self.host = settings.ollama.host.rstrip("/")
        self.model = settings.ollama.model
        self.timeout = settings.ollama.timeout_seconds
        self.client = httpx.AsyncClient(timeout=self.timeout)

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        reraise=True,
    )
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 500,
        format_json: bool = False,
    ) -> str:
        """Generate text completion from Ollama."""
        payload = {
            "model": self.model,
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

        try:
            response = await self.client.post(f"{self.host}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        embeddings = []
        for text in texts:
            try:
                response = await self.client.post(
                    f"{self.host}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                response.raise_for_status()
                data = response.json()
                embeddings.append(data.get("embedding", []))
            except Exception as e:
                logger.error(f"Embedding generation failed: {e}")
                embeddings.append([])
        return embeddings

    async def health_check(self) -> bool:
        """Check if Ollama is running and model is available."""
        try:
            response = await self.client.get(f"{self.host}/api/tags")
            response.raise_for_status()
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            return self.model in models or len(models) > 0
        except Exception:
            return False

    async def close(self):
        await self.client.aclose()


class UnifiedLLMClient:
    """Unified interface wrapping OpenCode Zen, Ollama, and Fallback."""
    def __init__(self):
        self.zen_client = OpenCodeZenClient()
        self.ollama_client = OllamaClient()

    @property
    def active_provider(self) -> str:
        return getattr(settings.llm, "provider", "opencode_zen")

    @property
    def active_model(self) -> str:
        if self.active_provider == "opencode_zen":
            return self.zen_client.model
        return self.ollama_client.model

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 500,
        format_json: bool = False,
    ) -> str:
        """Generate text using primary provider with automatic failover."""
        provider = self.active_provider

        # 1. If OpenCode Zen configured
        if provider in ("opencode_zen", "auto"):
            if self.zen_client.api_key:
                try:
                    return await self.zen_client.generate(
                        prompt=prompt,
                        system=system,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        format_json=format_json,
                    )
                except Exception as e:
                    logger.warning(f"OpenCode Zen error, attempting Ollama fallback: {e}")

        # 2. Try Ollama
        try:
            return await self.ollama_client.generate(
                prompt=prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
                format_json=format_json,
            )
        except Exception as e:
            logger.warning(f"Ollama error: {e}")
            raise

    async def health_check(self) -> Dict[str, Any]:
        """Check status of available LLM backends."""
        zen_ok = await self.zen_client.health_check()
        ollama_ok = await self.ollama_client.health_check()
        return {
            "opencode_zen": {
                "healthy": zen_ok,
                "model": self.zen_client.model,
                "base_url": self.zen_client.base_url,
            },
            "ollama": {
                "healthy": ollama_ok,
                "model": self.ollama_client.model,
                "host": self.ollama_client.host,
            },
            "active_provider": self.active_provider,
            "active_model": self.active_model,
        }

    async def close(self):
        await self.zen_client.close()
        await self.ollama_client.close()


# Singleton instance
_unified_client: Optional[UnifiedLLMClient] = None
_ollama_client: Optional[OllamaClient] = None


def get_llm_client() -> UnifiedLLMClient:
    global _unified_client
    if _unified_client is None:
        _unified_client = UnifiedLLMClient()
    return _unified_client


def get_ollama_client() -> OllamaClient:
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient()
    return _ollama_client