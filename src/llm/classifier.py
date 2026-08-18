import re
import logging
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass, field, asdict

from .client import get_ollama_client, get_llm_client
from .prompts import (
    build_intent_prompt,
    build_reply_prompt,
    build_deep_analysis_prompt,
    parse_intent_response,
    extract_json_from_text,
    VALID_INTENT_TAGS,
)
from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class IntentResult:
    tag: str
    confidence: float
    is_fallback: bool = False


@dataclass
class ReplyResult:
    content: str
    model: str
    is_fallback: bool = False


@dataclass
class PostAnalysisResult:
    summary: str
    what_it_means: str
    what_it_requires: str
    mentioned_products: List[str]
    pain_keywords: List[str]
    urgency: str
    sentiment: str
    opportunity_score: int
    buy_signal_strength: int
    engagement_potential: int
    recommended_angle: str
    reddit_context: str
    community_signals: str
    is_fallback: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HeuristicClassifier:
    """Rule-based classifier used as fallback when LLM is unavailable."""

    BUY_PATTERNS = [
        r"\b(looking for|need|recommend|recommendation|alternative to|switch from|best tool|pricing|budget|software for|service for|how much does|where can i buy|worth buying)\b",
        r"\b(buy|purchase|subscribe|cost|quote|hire|paying for)\b",
    ]
    PAIN_PATTERNS = [
        r"\b(frustrated|hate|broken|buggy|slow|terrible|awful|crashed|nightmare|struggling with|annoying|fails|error|issue with|can't figure out)\b",
        r"\b(sucks|useless|waste of time|headache|pain in the)\b",
    ]
    COMPETITOR_PATTERNS = [
        r"\b(left|leaving|switched from|tired of|cancelling|canceling|too expensive|price hike|unreliable|downgraded)\b",
    ]
    SEEKING_ALT_PATTERNS = [
        r"\b(looking for an alternative|any alternatives|replace|replacement for|move away from|migrate from|what should i use instead)\b",
    ]
    QUESTION_PATTERNS = [
        r"\b(how do i|why does|what is|is there a|anyone know|how to|does anyone|can someone explain|thoughts on)\b",
        r"\?",
    ]
    PRAISE_PATTERNS = [
        r"\b(love|amazing|game changer|incredible|fantastic|great job|kudos|shoutout|highly recommend|best experience)\b",
    ]
    SUCCESS_PATTERNS = [
        r"\b(finally|achieved|solved|working now|fixed|after months|milestone|launched|shipped|did it)\b",
    ]
    VENTING_PATTERNS = [
        r"\b(rant|venting|i can't believe|this is insane|wtf|what the hell|absolutely ridiculous|done with)\b",
    ]

    @classmethod
    def classify(cls, text: str) -> IntentResult:
        text_lower = text.lower()

        for pattern in cls.SEEKING_ALT_PATTERNS:
            if re.search(pattern, text_lower):
                return IntentResult(tag="seeking-alternatives", confidence=0.80, is_fallback=True)

        for pattern in cls.COMPETITOR_PATTERNS:
            if re.search(pattern, text_lower):
                return IntentResult(tag="competitor-complaint", confidence=0.75, is_fallback=True)

        for pattern in cls.BUY_PATTERNS:
            if re.search(pattern, text_lower):
                return IntentResult(tag="buy-intent", confidence=0.80, is_fallback=True)

        for pattern in cls.PAIN_PATTERNS:
            if re.search(pattern, text_lower):
                return IntentResult(tag="pain-point", confidence=0.75, is_fallback=True)

        for pattern in cls.VENTING_PATTERNS:
            if re.search(pattern, text_lower):
                return IntentResult(tag="venting", confidence=0.70, is_fallback=True)

        for pattern in cls.SUCCESS_PATTERNS:
            if re.search(pattern, text_lower):
                return IntentResult(tag="success-story", confidence=0.70, is_fallback=True)

        for pattern in cls.QUESTION_PATTERNS:
            if re.search(pattern, text_lower):
                return IntentResult(tag="question", confidence=0.70, is_fallback=True)

        for pattern in cls.PRAISE_PATTERNS:
            if re.search(pattern, text_lower):
                return IntentResult(tag="praise", confidence=0.75, is_fallback=True)

        return IntentResult(tag="other", confidence=0.40, is_fallback=True)


class IntentClassifier:
    def __init__(self):
        self.client = get_llm_client()

    async def classify(self, content: str) -> IntentResult:
        """Classify the intent of a Reddit post using LLM with heuristic fallback."""
        prompt = build_intent_prompt(content)

        try:
            response = await self.client.generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=100,
                format_json=True,
            )
            tag, confidence = parse_intent_response(response)
            logger.debug(f"Classified as '{tag}' (confidence: {confidence:.2f})")
            return IntentResult(tag=tag, confidence=confidence, is_fallback=False)
        except Exception as e:
            logger.warning(f"LLM intent classification unavailable ({e}). Using heuristic fallback.")
            return HeuristicClassifier.classify(content)


class ReplyGenerator:
    def __init__(self):
        self.client = get_llm_client()

    async def generate_reply(
        self,
        source: str,
        title: str,
        content: str,
        intent_tag: str,
        tone: str = "casual",
        subreddit: str = "reddit",
    ) -> ReplyResult:
        """Generate a Reddit-authentic reply for a mention."""
        prompt = build_reply_prompt(source, title, content, intent_tag, subreddit=subreddit, tone=tone)

        try:
            system_msg = (
                "You are an authentic, experienced Reddit community member. "
                "CRITICAL: Do NOT output any reasoning, thought traces, planning steps, or numbered outlines. "
                "Directly output ONLY your final suggested reply enclosed in <reply>...</reply> tags. "
                "Sound like a real person, not a marketer or assistant."
            )
            response = await self.client.generate(
                prompt=prompt,
                system=system_msg,
                temperature=0.5,
                max_tokens=1200,
            )
            reply = self._clean_reply_text(response, title, intent_tag)
            logger.debug(f"Generated reply ({len(reply)} chars)")
            model_name = self.client.active_model
            return ReplyResult(content=reply, model=model_name, is_fallback=False)
        except Exception as e:
            logger.warning(f"LLM reply generation unavailable ({e}). Generating template draft.")
            return self._generate_fallback_draft(source, title, intent_tag)

    def _clean_reply_text(self, text: str, title: str = "", intent_tag: str = "") -> str:
        """Extract and clean the genuine reply text from LLM response."""
        clean = text.strip()

        # 1. Look for explicit <reply>...</reply> tag
        reply_match = re.search(r"<reply>(.*?)</reply>", clean, flags=re.DOTALL | re.IGNORECASE)
        if reply_match:
            return reply_match.group(1).strip()

        # 2. Remove <think>...</think> blocks
        clean = re.sub(r"<think>.*?</think>", "", clean, flags=re.DOTALL).strip()

        # 3. Handle common draft markers
        draft_match = re.findall(
            r"(?:Draft|Drafting - Option \d+|Suggested Response|Suggested Reply):\s*\n(.*?)(?=\n\s*(?:Drafting -|Check |Sentence |\d+\.|\Z))",
            clean,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if draft_match:
            candidate = draft_match[-1].strip()
            candidate = re.split(r"Check constraints:|Constraint check:|Check sentence", candidate, flags=re.IGNORECASE)[0].strip()
            if len(candidate) > 20:
                return candidate

        # 4. Extract final reply markers
        markers = [
            "**Draft - Attempt 1 (Mental):**", "**Draft - Attempt 1:**", "**Draft Attempt 1:**",
            "**Draft Response:**", "**Draft Reply:**", "**Suggested Reply:**",
            "**Reply:**", "**Response:**", "Suggested Reply:", "Final Response:", "Final Answer:"
        ]
        for marker in markers:
            if marker in clean:
                candidate = clean.split(marker)[-1].strip()
                candidate = re.split(r"Check constraints:|Constraint check:|Check sentence", candidate, flags=re.IGNORECASE)[0].strip()
                if len(candidate) > 20:
                    clean = candidate
                    break

        # 5. If model output analysis steps, extract last paragraph
        if clean.startswith("1.") or "**Analyze" in clean[:60] or "thinking process" in clean[:40].lower():
            quotes = re.findall(r'"([^"]{25,})"', clean)
            if quotes:
                clean = quotes[-1].strip()
            else:
                paras = [p.strip() for p in clean.split("\n\n") if p.strip()]
                for p in reversed(paras):
                    p_clean = re.sub(r"Check constraints:.*|Check sentence.*", "", p, flags=re.DOTALL | re.IGNORECASE).strip()
                    if not re.match(r"^\d+\.", p_clean) and not p_clean.startswith("**") and len(p_clean) > 25:
                        clean = p_clean
                        break

        # 6. Clean meta-commentary intro lines
        if clean.startswith("Here") and ("reply" in clean.lower() or ":" in clean[:40]):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:]).strip()

        # 7. Strip outer quotes
        if (clean.startswith('"') and clean.endswith('"')) or (clean.startswith("'") and clean.endswith("'")):
            clean = clean[1:-1].strip()

        return clean

    def _generate_fallback_draft(self, source: str, title: str, intent_tag: str) -> ReplyResult:
        """Generate a clean template draft when LLM is offline."""
        if intent_tag in ("buy-intent", "seeking-alternatives"):
            content = f"Have you checked out tools with active communities around this? For {title or 'this use case'}, it's worth looking at both self-hosted and SaaS options depending on your scale and budget."
        elif intent_tag == "pain-point":
            content = f"This is a known pain point. The usual fix is to verify your configuration first, then check if there are open issues in the repo. Has this been happening since a specific version update?"
        elif intent_tag == "competitor-complaint":
            content = "A lot of teams have moved away from similar setups for the same reason. Worth looking at open-source alternatives that give you more control over pricing and data."
        elif intent_tag == "question":
            content = f"Good question. The most reliable approach for {title or 'this'} is to start with the official docs, then cross-reference with the community wiki — things change fast in this space."
        elif intent_tag == "venting":
            content = "Frustrating situation — I've been there. Usually it takes a few iterations to get the config right. Happy to dig into specifics if you share more details."
        elif intent_tag == "success-story":
            content = "Nice work getting that sorted! Would love to hear more about your approach — this kind of thing is always useful for others hitting the same wall."
        else:
            content = "Interesting perspective — this is worth a deeper look. The community here usually has solid takes on this kind of thing."

        return ReplyResult(content=content, model="heuristic-fallback", is_fallback=True)


class PostAnalyzer:
    """Deeply analyzes Reddit posts with community context, signals, and product intelligence."""

    def __init__(self):
        self.client = get_llm_client()

    async def analyze(
        self,
        source: str,
        title: str,
        content: str,
        subreddit: str = "",
        post_type: str = "text",
        post_flair: str = "",
        score: int = 0,
        num_comments: int = 0,
        upvote_ratio: float = 0.0,
        posted_at: str = "",
    ) -> PostAnalysisResult:
        prompt = build_deep_analysis_prompt(
            source=source,
            title=title,
            content=content,
            subreddit=subreddit,
            post_type=post_type,
            post_flair=post_flair or "",
            score=score,
            num_comments=num_comments,
            upvote_ratio=upvote_ratio,
            posted_at=posted_at,
        )
        system_msg = "You are an elite Reddit intelligence and product analyst. Return ONLY valid JSON matching the exact requested schema. No markdown, no preamble."

        try:
            response = await self.client.generate(
                prompt=prompt,
                system=system_msg,
                temperature=0.2,
                max_tokens=900,
                format_json=True,
            )
            data = extract_json_from_text(response)
            if data and isinstance(data, dict) and "summary" in data:

                def _to_str_list(val) -> List[str]:
                    if isinstance(val, list):
                        return [str(v).strip() for v in val if str(v).strip()]
                    if isinstance(val, str):
                        return [v.strip() for v in val.split(",") if v.strip()]
                    return []

                def _safe_int(val, default=0) -> int:
                    try:
                        return max(0, min(100, int(val)))
                    except (ValueError, TypeError):
                        return default

                return PostAnalysisResult(
                    summary=str(data.get("summary", "")).strip() or f"Reddit discussion in r/{subreddit} regarding {title}.",
                    what_it_means=str(data.get("what_it_means", "")).strip() or "User is seeking solutions or discussing community topics.",
                    what_it_requires=str(data.get("what_it_requires", "")).strip() or "Specific tool, feature, or answer.",
                    mentioned_products=_to_str_list(data.get("mentioned_products", [])),
                    pain_keywords=_to_str_list(data.get("pain_keywords", [])),
                    urgency=str(data.get("urgency", "Medium")).strip(),
                    sentiment=str(data.get("sentiment", "Inquiring")).strip(),
                    opportunity_score=_safe_int(data.get("opportunity_score", 60), 60),
                    buy_signal_strength=_safe_int(data.get("buy_signal_strength", 0), 0),
                    engagement_potential=_safe_int(data.get("engagement_potential", 50), 50),
                    recommended_angle=str(data.get("recommended_angle", "")).strip() or "Engage authentically with a concrete, helpful response.",
                    reddit_context=str(data.get("reddit_context", "")).strip() or f"Standard r/{subreddit} post.",
                    community_signals=str(data.get("community_signals", "")).strip() or f"{score} upvotes, {num_comments} comments.",
                    is_fallback=False,
                )
        except Exception as e:
            logger.warning(f"AI post analysis unavailable ({e}). Generating heuristic analysis.")

        return self._generate_fallback_analysis(source, title, content, subreddit, score, num_comments)

    def _generate_fallback_analysis(
        self,
        source: str,
        title: str,
        content: str,
        subreddit: str = "",
        score: int = 0,
        num_comments: int = 0,
    ) -> PostAnalysisResult:
        """Rule-based Reddit post analysis when LLM is unavailable."""
        full_text = f"{title or ''} {content or ''}".strip()
        text_lower = full_text.lower()

        sentences = [s.strip() for s in re.split(r"[.!?\n]", full_text) if len(s.strip()) > 10]
        summary = ". ".join(sentences[:2]) + "." if sentences else (title or "Reddit community discussion.")

        if any(w in text_lower for w in ["pricing", "expensive", "cost", "cancel", "switch", "alternative"]):
            what_it_means = "The author is evaluating software costs or seeking cost-effective alternatives with better value."
            urgency = "High"
            sentiment = "Frustrated"
            opp_score = 85
            buy_signal = 75
        elif any(w in text_lower for w in ["slow", "bug", "broken", "fails", "error", "issue", "crash"]):
            what_it_means = "The author is dealing with a technical pain point or performance issue in their current stack."
            urgency = "High"
            sentiment = "Frustrated"
            opp_score = 80
            buy_signal = 40
        elif any(w in text_lower for w in ["how do i", "how to", "best way", "recommend", "looking for"]):
            what_it_means = "The author is actively seeking recommendations or best practices from experienced practitioners."
            urgency = "Medium"
            sentiment = "Inquiring"
            opp_score = 75
            buy_signal = 60
        elif any(w in text_lower for w in ["love", "amazing", "finally", "shipped", "launched"]):
            what_it_means = "The author is sharing a positive experience or success milestone with the community."
            urgency = "Low"
            sentiment = "Enthusiastic"
            opp_score = 50
            buy_signal = 20
        else:
            what_it_means = f"General community discussion in r/{subreddit} about tooling, workflows, or experiences."
            urgency = "Low"
            sentiment = "Neutral"
            opp_score = 55
            buy_signal = 20

        pain_kws = []
        for kw in ["slow", "expensive", "broken", "error", "painful", "complex", "frustrating"]:
            if kw in text_lower:
                pain_kws.append(kw)

        engagement_potential = min(100, max(0, int((score * 2 + num_comments * 3) / 5 + 40)))

        return PostAnalysisResult(
            summary=summary,
            what_it_means=what_it_means,
            what_it_requires="Specific tool recommendation, practical advice, or direct answer to the stated problem.",
            mentioned_products=[],
            pain_keywords=pain_kws,
            urgency=urgency,
            sentiment=sentiment,
            opportunity_score=opp_score,
            buy_signal_strength=buy_signal,
            engagement_potential=engagement_potential,
            recommended_angle=f"Engage in r/{subreddit} with a direct, helpful response. Share a concrete experience or specific resource. Avoid generic advice.",
            reddit_context=f"r/{subreddit} post with {score} upvotes and {num_comments} comments.",
            community_signals=f"{score} upvotes, {num_comments} comments — {'high' if score > 100 else 'moderate' if score > 20 else 'low'} engagement.",
            is_fallback=True,
        )


class LLMPipeline:
    """Combined pipeline for intent classification, deep post analysis, and reply drafting."""

    def __init__(self):
        self.classifier = IntentClassifier()
        self.generator = ReplyGenerator()
        self.analyzer = PostAnalyzer()

    async def process_mention(
        self,
        mention_id: int,
        source: str,
        title: str,
        content: str,
        subreddit: str = "",
        post_type: str = "text",
        post_flair: str = "",
        score: int = 0,
        num_comments: int = 0,
        upvote_ratio: float = 0.0,
        posted_at: str = "",
    ) -> Tuple[Optional[IntentResult], Optional[ReplyResult], Optional[PostAnalysisResult]]:
        """Process a single Reddit mention: classify intent, deeply analyze, and draft reply."""
        # 1. Classify intent
        intent_result = await self.classifier.classify(content)

        # 2. Deep Reddit post analysis
        analysis_result = await self.analyzer.analyze(
            source=source,
            title=title,
            content=content,
            subreddit=subreddit,
            post_type=post_type,
            post_flair=post_flair,
            score=score,
            num_comments=num_comments,
            upvote_ratio=upvote_ratio,
            posted_at=posted_at,
        )

        # 3. Generate reply for actionable intents
        reply_result = None
        actionable_tags = {"buy-intent", "pain-point", "competitor-complaint", "question", "seeking-alternatives"}
        if intent_result.tag in actionable_tags:
            reply_result = await self.generator.generate_reply(
                source=source,
                title=title,
                content=content,
                intent_tag=intent_result.tag,
                subreddit=subreddit,
            )

        return intent_result, reply_result, analysis_result


# Convenience functions
async def classify_intent(content: str) -> IntentResult:
    classifier = IntentClassifier()
    return await classifier.classify(content)


async def generate_reply(
    source: str,
    title: str,
    content: str,
    intent_tag: str,
    tone: str = "casual",
    subreddit: str = "reddit",
) -> ReplyResult:
    generator = ReplyGenerator()
    return await generator.generate_reply(source, title, content, intent_tag, tone=tone, subreddit=subreddit)


async def analyze_post(
    source: str,
    title: str,
    content: str,
    subreddit: str = "",
    post_type: str = "text",
    post_flair: str = "",
    score: int = 0,
    num_comments: int = 0,
    upvote_ratio: float = 0.0,
    posted_at: str = "",
) -> PostAnalysisResult:
    analyzer = PostAnalyzer()
    return await analyzer.analyze(
        source=source,
        title=title,
        content=content,
        subreddit=subreddit,
        post_type=post_type,
        post_flair=post_flair,
        score=score,
        num_comments=num_comments,
        upvote_ratio=upvote_ratio,
        posted_at=posted_at,
    )