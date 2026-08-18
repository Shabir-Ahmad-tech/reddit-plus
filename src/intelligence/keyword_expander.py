"""
AI Keyword Discovery & Expansion Engine.
Generates relevant keyword clusters and competitor queries from a seed topic.
"""

import json
import re
import logging
from typing import List

from .router import get_ai_router

logger = logging.getLogger(__name__)

EXPANSION_PROMPT = """You are a Reddit search intelligence expert.

Given the seed topic/product: "{seed}"

Generate 8 to 12 highly relevant search keywords/phrases that Reddit users actually type when discussing this topic, seeking alternatives, asking for recommendations, or expressing pain points.

Include:
- Alternative queries ("alternative to {seed}", "switch from {seed}")
- Problem queries ("trouble with {seed}", "{seed} pricing")
- Recommendation queries ("best tool for...", "{seed} consultant")

Output JSON only as an array of strings:
["keyword 1", "keyword 2", "keyword 3", ...]"""


class KeywordExpander:
    def __init__(self):
        self.router = get_ai_router()

    async def expand(self, seed: str) -> List[str]:
        if not seed or not seed.strip():
            return []

        prompt = EXPANSION_PROMPT.replace("{seed}", seed.strip())
        system_msg = "Output strictly a JSON array of strings. No explanation."

        try:
            raw = await self.router.generate(
                prompt=prompt,
                system=system_msg,
                task_type="expansion",
                temperature=0.4,
                max_tokens=300,
                format_json=True,
            )
            clean = raw.strip()
            clean = re.sub(r"<think>.*?</think>", "", clean, flags=re.DOTALL).strip()
            arr_match = re.search(r"(\[.*\])", clean, re.DOTALL)
            if arr_match:
                items = json.loads(arr_match.group(1))
                return [str(k).strip() for k in items if str(k).strip()]
        except Exception as e:
            logger.warning(f"Keyword expansion failed ({e}). Returning heuristic variations.")

        # Heuristic variations fallback
        s = seed.strip()
        return [
            f"{s} alternative",
            f"best {s}",
            f"switch from {s}",
            f"{s} pricing",
            f"how to use {s}",
            f"{s} workflow",
            f"{s} recommendations",
            f"replace {s}",
        ]
