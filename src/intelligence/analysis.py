"""
Deep Reddit Post & Community Analysis Engine.
Analyzes post text, metadata, and top community comments.
"""

import re
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any

from .router import get_ai_router
from src.database.models import RedditPost, RedditComment

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT_TEMPLATE = """You are a senior Reddit market intelligence and conversation analyst.

Analyze this Reddit discussion:

Subreddit: r/{subreddit}
Title: {title}
Post Type: {post_type} | Flair: {post_flair}
Score: {score} | Comments Count: {num_comments} | Upvote Ratio: {upvote_ratio}
Posted At: {posted_at}

Post Content:
---
{content}
---

{comments_section}

Provide a comprehensive structured analysis. Respond ONLY with valid JSON matching this schema:
{{
  "summary": "2-3 sentence executive summary of what this post is about.",
  "what_it_means": "Strategic explanation of the underlying problem, business implication, or user frustration.",
  "what_it_requires": "What the user specifically needs (tool, feature, workaround, or advice).",
  "urgency": "High | Medium | Low",
  "sentiment": "Frustrated | Inquiring | Solution-Seeking | Critical | Enthusiastic | Neutral | Venting",
  "buy_signal_strength": 0-100,
  "pain_strength": 0-100,
  "engagement_potential": 0-100,
  "mentioned_products": ["product1", "product2"],
  "pain_keywords": ["slow", "expensive", "confusing"],
  "requirements": ["must support Python", "needs real-time alerts"],
  "goals": ["automate marketing", "reduce server cost"],
  "competitors": ["HubSpot", "Zapier"],
  "recommended_angle": "Concrete advice on how a community member should reply: angle to take, value to add, what NOT to do.",
  "reddit_context": "Subreddit culture notes and how to blend in naturally.",
  "community_signals": "Summary of what top commenters are saying and community sentiment."
}}"""


@dataclass
class DeepAnalysisResult:
    summary: str
    what_it_means: str
    what_it_requires: str
    urgency: str = "Medium"
    sentiment: str = "Inquiring"
    buy_signal_strength: int = 50
    pain_strength: int = 50
    engagement_potential: int = 50
    mentioned_products: List[str] = field(default_factory=list)
    pain_keywords: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    goals: List[str] = field(default_factory=list)
    competitors: List[str] = field(default_factory=list)
    recommended_angle: str = ""
    reddit_context: str = ""
    community_signals: str = ""
    is_fallback: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PostAnalyzer:
    def __init__(self):
        self.router = get_ai_router()

    async def analyze(
        self,
        post: RedditPost,
        top_comments: Optional[List[RedditComment]] = None,
    ) -> DeepAnalysisResult:
        comments_text = ""
        if top_comments:
            c_lines = []
            for i, c in enumerate(top_comments[:5], 1):
                c_lines.append(f"Comment #{i} by u/{c.author} (▲ {c.score}): {c.body[:300]}")
            comments_text = "Top Community Comments:\n---\n" + "\n\n".join(c_lines) + "\n---"

        prompt = ANALYSIS_PROMPT_TEMPLATE
        prompt = prompt.replace("{subreddit}", post.subreddit or "all")
        prompt = prompt.replace("{title}", post.title or "Untitled")
        prompt = prompt.replace("{post_type}", post.post_type or "text")
        prompt = prompt.replace("{post_flair}", post.post_flair or "none")
        prompt = prompt.replace("{score}", str(post.score or 0))
        prompt = prompt.replace("{num_comments}", str(post.num_comments or 0))
        prompt = prompt.replace("{upvote_ratio}", f"{int((post.upvote_ratio or 0.0) * 100)}%")
        prompt = prompt.replace("{posted_at}", post.posted_at.isoformat() if post.posted_at else "recent")
        prompt = prompt.replace("{content}", (post.body or post.title or "")[:2500])
        prompt = prompt.replace("{comments_section}", comments_text)

        system_msg = "You are an elite Reddit intelligence analyst. Output strictly valid JSON only. No formatting markup outside JSON."

        try:
            raw_response = await self.router.generate(
                prompt=prompt,
                system=system_msg,
                task_type="analysis",
                temperature=0.2,
                max_tokens=950,
                format_json=True,
            )
            return self._parse_analysis(raw_response, post)
        except Exception as e:
            logger.warning(f"AI post analysis failed ({e}). Generating heuristic analysis.")
            return self._heuristic_analysis(post)

    def _parse_analysis(self, raw: str, post: RedditPost) -> DeepAnalysisResult:
        clean = raw.strip()
        clean = re.sub(r"<think>.*?</think>", "", clean, flags=re.DOTALL).strip()

        data = {}
        # Try full json parse or regex extract
        json_match = re.search(r"(\{.*\})", clean, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
            except Exception:
                pass

        if not data or not isinstance(data, dict):
            return self._heuristic_analysis(post)

        def _to_list(val) -> List[str]:
            if isinstance(val, list):
                return [str(v).strip() for v in val if str(v).strip()]
            if isinstance(val, str) and val.strip():
                return [s.strip() for s in val.split(",") if s.strip()]
            return []

        def _to_int(val, default: int = 50) -> int:
            try:
                return max(0, min(100, int(val)))
            except Exception:
                return default

        return DeepAnalysisResult(
            summary=str(data.get("summary") or f"Reddit discussion in r/{post.subreddit} regarding {post.title}.").strip(),
            what_it_means=str(data.get("what_it_means") or "User is seeking solutions or discussing workflows.").strip(),
            what_it_requires=str(data.get("what_it_requires") or "Direct advice or tool recommendation.").strip(),
            urgency=str(data.get("urgency") or "Medium").strip(),
            sentiment=str(data.get("sentiment") or "Inquiring").strip(),
            buy_signal_strength=_to_int(data.get("buy_signal_strength"), 50),
            pain_strength=_to_int(data.get("pain_strength"), 50),
            engagement_potential=_to_int(data.get("engagement_potential"), 50),
            mentioned_products=_to_list(data.get("mentioned_products")),
            pain_keywords=_to_list(data.get("pain_keywords")),
            requirements=_to_list(data.get("requirements")),
            goals=_to_list(data.get("goals")),
            competitors=_to_list(data.get("competitors")),
            recommended_angle=str(data.get("recommended_angle") or "Engage constructively with specific experience.").strip(),
            reddit_context=str(data.get("reddit_context") or f"Standard r/{post.subreddit} post.").strip(),
            community_signals=str(data.get("community_signals") or f"{post.score} upvotes, {post.num_comments} comments.").strip(),
            is_fallback=False,
        )

    def _heuristic_analysis(self, post: RedditPost) -> DeepAnalysisResult:
        full_text = f"{post.title or ''} {post.body or ''}".lower()
        pain_kws = [w for w in ["slow", "expensive", "broken", "bug", "pricing", "alternative", "issue", "crash"] if w in full_text]

        buy_signal = 75 if any(w in full_text for w in ["buy", "purchase", "pricing", "alternative", "recommend", "best tool"]) else 30
        pain_score = 80 if any(w in full_text for w in ["hate", "broken", "slow", "terrible", "frustrating", "crashed"]) else 40
        engagement = min(100, max(20, int((post.score * 2 + post.num_comments * 3) + 30)))

        return DeepAnalysisResult(
            summary=f"Discussion in r/{post.subreddit}: {post.title}",
            what_it_means="The author is discussing challenges or exploring alternatives in their current setup.",
            what_it_requires="Practical recommendations or troubleshooting advice.",
            urgency="High" if (buy_signal > 60 or pain_score > 60) else "Medium",
            sentiment="Frustrated" if pain_score > 60 else "Inquiring",
            buy_signal_strength=buy_signal,
            pain_strength=pain_score,
            engagement_potential=engagement,
            mentioned_products=[],
            pain_keywords=pain_kws,
            requirements=["Practical solution", "Reliable workflow"],
            goals=["Resolve current issue"],
            competitors=[],
            recommended_angle=f"Share a helpful, direct experience in r/{post.subreddit} without pitch language.",
            reddit_context=f"Community r/{post.subreddit} context.",
            community_signals=f"{post.score} upvotes, {post.num_comments} comments.",
            is_fallback=True,
        )
