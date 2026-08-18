"""
Multi-Strategy Reply Generator.
Drafts authentic Reddit responses with strategy selection and critic evaluation.
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any

from src.intelligence.router import get_ai_router
from .strategies import STRATEGY_DESCRIPTIONS, REPLY_SYSTEM_PROMPT
from .critic import ReplyCritic, CriticEvaluation

logger = logging.getLogger(__name__)


@dataclass
class GeneratedReplyResult:
    content: str
    strategy: str
    model_used: str
    critic: CriticEvaluation
    is_fallback: bool = False


class ReplyGenerator:
    def __init__(self):
        self.router = get_ai_router()
        self.critic = ReplyCritic()

    async def generate_reply(
        self,
        title: str,
        content: str,
        subreddit: str = "all",
        intent_tag: str = "question",
        strategy: str = "DIRECT_ANSWER",
        recommended_angle: Optional[str] = None,
        product_context: Optional[str] = None,
    ) -> GeneratedReplyResult:
        strategy_desc = STRATEGY_DESCRIPTIONS.get(strategy, STRATEGY_DESCRIPTIONS["DIRECT_ANSWER"])

        prompt = f"""Subreddit: r/{subreddit}
Post Title: {title}
Post Content:
---
{content[:2000] if content else 'No body text'}
---

Detected Intent: {intent_tag}
Strategy: {strategy} — {strategy_desc}
"""
        if recommended_angle:
            prompt += f"\nRecommended Angle: {recommended_angle}"
        if product_context:
            prompt += f"\nProduct/Service Knowledge: {product_context} (Only mention if natural and follows the strategy!)"

        prompt += "\nWrite the reply now. Output ONLY inside <reply>...</reply> tags."

        try:
            raw = await self.router.generate(
                prompt=prompt,
                system=REPLY_SYSTEM_PROMPT,
                task_type="reply",
                temperature=0.4,
                max_tokens=600,
            )
            cleaned_text = self._clean_reply(raw, title)

            # Run critic evaluation
            eval_result = await self.critic.evaluate(
                reply=cleaned_text,
                title=title,
                content=content,
                subreddit=subreddit,
            )

            # If promotion risk is too high and not already NO_PROMOTION, try regenerating with NO_PROMOTION strategy
            if not eval_result.is_safe and strategy != "NO_PROMOTION":
                logger.info(f"Reply flagged with promotion risk ({eval_result.promotion_risk}). Auto-regenerating with NO_PROMOTION strategy...")
                return await self.generate_reply(
                    title=title,
                    content=content,
                    subreddit=subreddit,
                    intent_tag=intent_tag,
                    strategy="NO_PROMOTION",
                    recommended_angle="Focus purely on technical/practical help with zero pitch.",
                )

            return GeneratedReplyResult(
                content=cleaned_text,
                strategy=strategy,
                model_used=self.router.active_model,
                critic=eval_result,
                is_fallback=False,
            )
        except Exception as e:
            logger.warning(f"AI reply generation failed ({e}). Generating template fallback.")
            fallback_text = self._fallback_template(title, intent_tag, strategy)
            critic_eval = CriticEvaluation(authenticity=75, relevance=80, helpfulness=75, promotion_risk=10, is_safe=True)
            return GeneratedReplyResult(
                content=fallback_text,
                strategy=strategy,
                model_used="heuristic-fallback",
                critic=critic_eval,
                is_fallback=True,
            )

    def _clean_reply(self, raw: str, title: str) -> str:
        clean = raw.strip()

        # 1. Extract <reply>...</reply>
        match = re.search(r"<reply>(.*?)</reply>", clean, flags=re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # 2. Strip thinking tags
        clean = re.sub(r"<think>.*?</think>", "", clean, flags=re.DOTALL).strip()

        # 3. Strip markdown quote wrappers
        if (clean.startswith('"') and clean.endswith('"')) or (clean.startswith("'") and clean.endswith("'")):
            clean = clean[1:-1].strip()

        # 4. If multiline analysis occurred, grab last clean paragraph
        paragraphs = [p.strip() for p in clean.split("\n\n") if p.strip()]
        for p in reversed(paragraphs):
            if not p.startswith("**") and not p.startswith("1.") and len(p) > 20:
                return p

        return clean

    def _fallback_template(self, title: str, intent_tag: str, strategy: str) -> str:
        if intent_tag in ("buy-intent", "seeking-alternatives"):
            return f"For this use case, check tools with active community ecosystems. It's usually worth comparing self-hosted vs managed setups before deciding on pricing."
        elif intent_tag == "pain-point":
            return f"Ran into a similar issue recently. Usually the quickest fix is checking your middleware config or reviewing open GitHub issues on the repo."
        return f"Good question — the most reliable approach is starting with the official docs, then testing a minimal reproducible setup."
