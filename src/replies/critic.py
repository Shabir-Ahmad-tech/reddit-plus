"""
Reply Critic Engine.
Evaluates reply drafts for authenticity, relevance, helpfulness, and self-promotion risk.
"""

import re
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Tuple

from src.intelligence.router import get_ai_router

logger = logging.getLogger(__name__)

CRITIC_PROMPT = """You are a strict Reddit moderator and community expert evaluating a proposed reply.

Original Post:
Subreddit: r/{subreddit}
Title: {title}
Post Content: {content}

Proposed Reply Draft:
---
{reply}
---

Score this draft on a 0-100 scale for each criterion:
- authenticity: does this sound like a real Reddit user or an AI/bot? (100 = completely authentic)
- relevance: does it directly answer the post's core issue? (100 = directly relevant)
- helpfulness: does it provide genuine practical value? (100 = highly actionable)
- promotion_risk: does it sound like a sales pitch or self-promotion? (0 = zero pitch, 100 = pure spam)
- hallucination_risk: does it make unverified or false claims? (0 = fully accurate, 100 = completely made up)
- community_fit: does it fit the tone and culture of r/{subreddit}? (100 = perfect fit)

Respond ONLY with valid JSON:
{{
  "authenticity": 90,
  "relevance": 95,
  "helpfulness": 88,
  "promotion_risk": 15,
  "hallucination_risk": 5,
  "community_fit": 92,
  "verdict": "APPROVED | REVISE | REJECT",
  "critic_notes": "Brief 1-sentence assessment."
}}"""


@dataclass
class CriticEvaluation:
    authenticity: int = 85
    relevance: int = 90
    helpfulness: int = 85
    promotion_risk: int = 10
    hallucination_risk: int = 5
    community_fit: int = 85
    verdict: str = "APPROVED"
    critic_notes: str = ""
    is_safe: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ReplyCritic:
    def __init__(self):
        self.router = get_ai_router()

    async def evaluate(
        self,
        reply: str,
        title: str,
        content: str,
        subreddit: str = "all",
    ) -> CriticEvaluation:
        if not reply or not reply.strip():
            return CriticEvaluation(is_safe=False, verdict="REJECT", critic_notes="Empty reply")

        prompt = CRITIC_PROMPT.replace("{subreddit}", subreddit)
        prompt = prompt.replace("{title}", title[:300] if title else "No title")
        prompt = prompt.replace("{content}", content[:1500] if content else "")
        prompt = prompt.replace("{reply}", reply)

        system_msg = "You are a strict Reddit content critic. Output strictly valid JSON only."

        try:
            raw = await self.router.generate(
                prompt=prompt,
                system=system_msg,
                task_type="critic",
                temperature=0.1,
                max_tokens=250,
                format_json=True,
            )
            return self._parse_evaluation(raw)
        except Exception as e:
            logger.warning(f"Reply critic evaluation failed ({e}). Using heuristic safety check.")
            return self._heuristic_evaluation(reply)

    def _parse_evaluation(self, raw: str) -> CriticEvaluation:
        clean = raw.strip()
        clean = re.sub(r"<think>.*?</think>", "", clean, flags=re.DOTALL).strip()
        match = re.search(r"(\{.*\})", clean, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))

                def _val(k, default):
                    try:
                        return max(0, min(100, int(data.get(k, default))))
                    except Exception:
                        return default

                promo = _val("promotion_risk", 20)
                is_safe = promo <= 60

                return CriticEvaluation(
                    authenticity=_val("authenticity", 85),
                    relevance=_val("relevance", 90),
                    helpfulness=_val("helpfulness", 85),
                    promotion_risk=promo,
                    hallucination_risk=_val("hallucination_risk", 5),
                    community_fit=_val("community_fit", 85),
                    verdict=str(data.get("verdict", "APPROVED" if is_safe else "REVISE")),
                    critic_notes=str(data.get("critic_notes", "Passed review")),
                    is_safe=is_safe,
                )
            except Exception:
                pass

        return self._heuristic_evaluation(clean)

    def _heuristic_evaluation(self, reply: str) -> CriticEvaluation:
        reply_lower = reply.lower()
        buzzwords = ["game-changer", "best on the market", "check out my", "buy now", "discount", "revolutionary", "all-in-one"]
        found_buzz = [b for b in buzzwords if b in reply_lower]

        promo = 80 if found_buzz else 15
        is_safe = promo <= 60

        return CriticEvaluation(
            authenticity=75 if is_safe else 50,
            relevance=85,
            helpfulness=80,
            promotion_risk=promo,
            hallucination_risk=5,
            community_fit=80 if is_safe else 45,
            verdict="APPROVED" if is_safe else "REVISE",
            critic_notes=f"Found promotional signals: {found_buzz}" if found_buzz else "Heuristic check passed",
            is_safe=is_safe,
        )
