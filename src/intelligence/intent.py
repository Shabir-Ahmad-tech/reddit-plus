"""
Granular Intent Classifier.
Categorizes Reddit conversations into 10+ granular intent classes.
"""

import re
import json
import logging
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any

from .router import get_ai_router

logger = logging.getLogger(__name__)

VALID_INTENT_TAGS = [
    "buy-intent",
    "pain-point",
    "competitor-complaint",
    "question",
    "seeking-alternatives",
    "venting",
    "praise",
    "success-story",
    "tool-review",
    "hiring",
    "other",
]

INTENT_PROMPT = """Classify this Reddit post's intent into ONE category. Output ONLY valid JSON — no preamble, no thinking traces.

Reddit Post:
---
{content}
---

Categories:
- buy-intent: User is actively looking to buy, subscribe, pay for, or hire a product/service.
- pain-point: User has a frustrating problem, bug, limitation, or blocker with a tool/workflow.
- competitor-complaint: User complains about or expresses desire to leave a competitor's product.
- seeking-alternatives: User explicitly wants to switch from something they currently use to an alternative.
- question: User asks for recommendations, advice, or how-to help.
- praise: User praises a product, workflow, or solution.
- venting: User is venting frustration with no clear search for a solution.
- success-story: User shares a positive milestone or achievement.
- tool-review: User is reviewing or comparing software/tools.
- hiring: Job posting or looking-for-work post.
- other: None of the above.

Confidence guide:
- 0.90-1.00: clear unambiguous signal
- 0.70-0.89: strong signal
- 0.50-0.69: moderate signal with some ambiguity
- 0.30-0.49: weak signal

Respond with JSON only:
{"tag": "category-name", "confidence": 0.85}"""


@dataclass
class IntentResult:
    tag: str
    confidence: float
    is_fallback: bool = False


class IntentClassifier:
    def __init__(self):
        self.router = get_ai_router()

    async def classify(self, content: str, title: Optional[str] = None) -> IntentResult:
        full_text = f"{title or ''}\n{content or ''}".strip()
        if not full_text:
            return IntentResult(tag="other", confidence=0.0, is_fallback=True)

        prompt = INTENT_PROMPT.replace("{content}", full_text[:2500])

        try:
            raw_response = await self.router.generate(
                prompt=prompt,
                task_type="classification",
                temperature=0.1,
                max_tokens=150,
                format_json=True,
            )
            tag, conf = self._parse_response(raw_response)
            return IntentResult(tag=tag, confidence=conf, is_fallback=False)
        except Exception as e:
            logger.warning(f"LLM intent classification failed ({e}). Using heuristic fallback.")
            return self._heuristic_fallback(full_text)

    def _parse_response(self, response: str) -> Tuple[str, float]:
        clean = response.strip()
        # Strip thinking traces
        clean = re.sub(r"<think>.*?</think>", "", clean, flags=re.DOTALL).strip()

        # Find JSON object
        json_matches = list(re.finditer(r"\{[^{}]*\"tag\"[^{}]*\}", clean, re.DOTALL))
        if json_matches:
            try:
                data = json.loads(json_matches[-1].group(0))
                tag = str(data.get("tag", "other")).lower().strip()
                conf = float(data.get("confidence", 0.7))
                if tag in VALID_INTENT_TAGS:
                    return tag, max(0.0, min(1.0, conf))
            except Exception:
                pass

        # Fallback keyword match in text
        response_lower = clean.lower()
        for valid in VALID_INTENT_TAGS:
            if valid in response_lower:
                return valid, 0.7

        return "other", 0.4

    def _heuristic_fallback(self, text: str) -> IntentResult:
        text_lower = text.lower()
        if any(w in text_lower for w in ["looking for an alternative", "switch from", "replace", "alternative to", "migrate from"]):
            return IntentResult(tag="seeking-alternatives", confidence=0.85, is_fallback=True)
        if any(w in text_lower for w in ["looking for", "need a tool", "recommend", "best software", "budget", "pricing", "where to buy"]):
            return IntentResult(tag="buy-intent", confidence=0.80, is_fallback=True)
        if any(w in text_lower for w in ["too expensive", "cancelling", "leaving", "tired of", "price hike"]):
            return IntentResult(tag="competitor-complaint", confidence=0.80, is_fallback=True)
        if any(w in text_lower for w in ["frustrated", "buggy", "broken", "slow", "terrible", "issue with", "nightmare", "struggling"]):
            return IntentResult(tag="pain-point", confidence=0.75, is_fallback=True)
        if any(w in text_lower for w in ["how do i", "how to", "why does", "is there a way", "?"]):
            return IntentResult(tag="question", confidence=0.70, is_fallback=True)
        return IntentResult(tag="other", confidence=0.40, is_fallback=True)
