import json
import re
from typing import Optional
from src.config import settings

# --- Intent Tags ---
VALID_INTENT_TAGS = [
    "buy-intent",
    "pain-point",
    "competitor-complaint",
    "question",
    "praise",
    "seeking-alternatives",
    "venting",
    "success-story",
    "tool-review",
    "hiring",
    "other",
]

# --- Intent Classification Prompt ---
INTENT_PROMPT_TEMPLATE = """Classify this Reddit post's intent. Output ONLY a JSON object — no thinking, no explanation, no preamble.

Reddit Post:
---
{content}
---

Choose ONE tag:
- buy-intent: actively researching, comparing, or ready to buy a product/tool/service
- pain-point: frustrated by a specific technical problem, bug, or limitation
- competitor-complaint: complaining about or leaving a competitor's product
- question: asking for advice, recommendations, or how-to help
- praise: happy with a product, service, or experience
- seeking-alternatives: explicitly wants to switch from something they currently use
- venting: emotional frustration without a clear solution-seeking goal
- success-story: sharing a positive outcome or achievement
- tool-review: reviewing or comparing tools/software
- hiring: job posting or looking-for-work
- other: none of the above

Confidence scoring guide:
- 0.9-1.0: extremely clear signal, no ambiguity
- 0.7-0.89: strong signal, mostly clear
- 0.5-0.69: moderate signal, some ambiguity
- 0.3-0.49: weak signal, could be multiple categories
- 0.1-0.29: very uncertain

OUTPUT FORMAT — respond with this exact JSON and nothing else:
{"tag": "category-name", "confidence": 0.85}"""

# --- Reply Generation Prompt (Reddit-native) ---
REPLY_PROMPT_TEMPLATE = """You are an experienced Reddit community member. Write a helpful, authentic reply to this Reddit post.

Subreddit: r/{subreddit}
Title: {title}
Post Content: {content}
Detected Intent: {intent_tag}

Reddit Reply Rules:
- Sound like a real person who has relevant experience, NOT a marketer or bot
- 2-4 sentences maximum — Reddit rewards concise, direct answers
- Match the subreddit's culture: technical subreddits expect technical replies, casual subreddits expect casual tone
- Do NOT use promotional language, bullet points, or numbered lists unless the OP used them
- Do NOT say "great question!", "I hope this helps!", or similar filler phrases
- Do NOT mention you're an AI
- Add genuine value: a specific tip, a personal experience angle, or a direct answer
- If relevant, mention a relevant subreddit or resource naturally
- Wrap your final reply in <reply>...</reply> tags"""

# --- Deep Reddit Analysis Prompt ---
DEEP_ANALYSIS_PROMPT_TEMPLATE = """You are a senior Reddit intelligence analyst specializing in community sentiment, product research, and engagement opportunities.

Analyze this Reddit post in detail:

Subreddit: r/{subreddit}
Post Title: {title}
Post Type: {post_type}
Post Flair: {post_flair}
Upvotes: {score} | Comments: {num_comments} | Upvote Ratio: {upvote_ratio}
Posted: {posted_at}

Post Content:
---
{content}
---

Provide a comprehensive JSON analysis matching this EXACT format:
{{
  "summary": "2-3 sentence executive summary of what this Reddit post is about and its community context.",
  "what_it_means": "Deep explanation of the underlying problem, frustration, market signal, or community sentiment. Include why this matters from a product/market perspective.",
  "what_it_requires": "What the OP needs — specific tool, feature, workflow change, or answer they are seeking.",
  "mentioned_products": ["product1", "product2"],
  "pain_keywords": ["keyword1", "keyword2", "keyword3"],
  "urgency": "High | Medium | Low",
  "sentiment": "Frustrated | Inquiring | Solution-Seeking | Critical | Enthusiastic | Neutral | Venting | Satisfied",
  "opportunity_score": 0-100,
  "buy_signal_strength": 0-100,
  "engagement_potential": 0-100,
  "recommended_angle": "Specific, strategic advice on how to reply to this post — what angle to take, what to say, what NOT to say. Be concrete and actionable.",
  "reddit_context": "Notes on the subreddit culture, community norms, or post flair significance that should inform how to engage.",
  "community_signals": "Observations about upvote count, comment count, engagement pattern, and what that tells us."
}}

Respond with valid JSON only. No markdown, no conversational text."""


def build_intent_prompt(content: str) -> str:
    """Build Reddit-aware intent classification prompt."""
    template = settings.ollama.intent_prompt or INTENT_PROMPT_TEMPLATE
    content_clean = content[:3000] if content else ""
    if "{content}" in template:
        return template.replace("{content}", content_clean)
    try:
        return template.format(content=content_clean)
    except Exception:
        return INTENT_PROMPT_TEMPLATE.replace("{content}", content_clean)


def build_reply_prompt(
    source: str,
    title: str,
    content: str,
    intent_tag: str,
    subreddit: str = "reddit",
    tone: str = "casual",
) -> str:
    """Build Reddit-native reply generation prompt."""
    template = settings.ollama.reply_prompt or REPLY_PROMPT_TEMPLATE
    res = template
    res = res.replace("{source}", source or "reddit")
    res = res.replace("{subreddit}", subreddit or "reddit")
    res = res.replace("{title}", (title[:500] if title else "No title"))
    res = res.replace("{content}", (content[:2000] if content else ""))
    res = res.replace("{intent_tag}", intent_tag or "other")
    if tone and tone not in ("casual", ""):
        res += f"\n\nTone preference: {tone}"
    return res


def build_deep_analysis_prompt(
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
) -> str:
    """Build Reddit-specific deep analysis prompt with all available signals."""
    res = DEEP_ANALYSIS_PROMPT_TEMPLATE
    res = res.replace("{subreddit}", subreddit or "unknown")
    res = res.replace("{title}", title[:500] if title else "No title")
    res = res.replace("{content}", content[:3000] if content else "")
    res = res.replace("{post_type}", post_type or "text")
    res = res.replace("{post_flair}", post_flair or "none")
    res = res.replace("{score}", str(score))
    res = res.replace("{num_comments}", str(num_comments))
    res = res.replace("{upvote_ratio}", f"{upvote_ratio:.0%}" if upvote_ratio else "unknown")
    res = res.replace("{posted_at}", posted_at or "unknown")
    return res


def extract_json_from_text(text: str) -> Optional[dict]:
    """Extract a JSON object from text that may contain markdown or surrounding text."""
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except Exception:
            pass

    json_match = re.search(r"(\{.*\})", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except Exception:
            pass

    return None


def parse_intent_response(response: str) -> tuple[str, float]:
    """Parse JSON response from intent classification with robust fallbacks.
    Handles reasoning models that output chain-of-thought before the final JSON.
    """
    clean = response.strip()

    # 1. Strip <think>...</think> blocks (DeepSeek-R1 style)
    clean = re.sub(r"<think>.*?</think>", "", clean, flags=re.DOTALL).strip()

    # 2. Strip reasoning preamble — find the last JSON object in the text
    #    Reasoning models often say "Let's analyze... {json}" — we want the json
    all_json_matches = list(re.finditer(r"\{[^{}]*\"tag\"[^{}]*\}", clean, re.DOTALL))
    if all_json_matches:
        # Use the LAST match — reasoning traces come before the answer
        last_match = all_json_matches[-1]
        try:
            data = json.loads(last_match.group(0))
            tag = str(data.get("tag", "other")).lower().strip()
            try:
                confidence = float(data.get("confidence", 0.5))
            except (ValueError, TypeError):
                confidence = 0.5
            if tag not in VALID_INTENT_TAGS:
                for valid_tag in VALID_INTENT_TAGS:
                    if valid_tag in tag or tag in valid_tag:
                        tag = valid_tag
                        break
                else:
                    tag = "other"
            confidence = max(0.0, min(1.0, confidence))
            return tag, confidence
        except Exception:
            pass

    # 3. Try the full extract_json_from_text on the cleaned text
    data = extract_json_from_text(clean)
    if data and isinstance(data, dict):
        tag = str(data.get("tag", "other")).lower().strip()
        try:
            confidence = float(data.get("confidence", 0.5))
        except (ValueError, TypeError):
            confidence = 0.5

        if tag not in VALID_INTENT_TAGS:
            for valid_tag in VALID_INTENT_TAGS:
                if valid_tag in tag or tag in valid_tag:
                    tag = valid_tag
                    break
            else:
                tag = "other"

        confidence = max(0.0, min(1.0, confidence))
        return tag, confidence

    # 4. Last resort: heuristic keyword search in raw text (returns 0.6 as signal that it's approximate)
    response_lower = clean.lower()
    for tag in VALID_INTENT_TAGS:
        if tag in response_lower:
            return tag, 0.6
    return "other", 0.0