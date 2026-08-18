"""
Keyword Matching Engine.
Supports exact phrases, multi-word tokens, negative keywords, and exclusion patterns.
"""

import re
from typing import List, Tuple, Dict, Any, Optional


class KeywordMatcher:
    """Matches text against keywords with phrase, exact, and negative exclusions."""

    @staticmethod
    def match_keyword(
        text: str,
        keyword: str,
        match_type: str = "phrase",
    ) -> Tuple[bool, float, Optional[str]]:
        """
        Check if text matches a keyword pattern.
        Returns (is_matched, confidence, reason).
        """
        if not text or not keyword:
            return False, 0.0, None

        text_lower = text.lower()
        kw_lower = keyword.strip().lower()

        # 1. Exact phrase boundary match
        pattern = r"\b" + re.escape(kw_lower) + r"\b"
        if re.search(pattern, text_lower):
            return True, 1.0, f"Exact phrase match: '{keyword}'"

        # 2. If broad/phrase match, check all tokens
        if match_type in ("phrase", "broad") and " " in kw_lower:
            tokens = [t for t in kw_lower.split() if len(t) > 2]
            if tokens and all(t in text_lower for t in tokens):
                return True, 0.85, f"All tokens matched: '{keyword}'"

        # 3. Simple substring match
        if kw_lower in text_lower:
            return True, 0.80, f"Keyword match: '{keyword}'"

        return False, 0.0, None

    @staticmethod
    def check_exclusions(text: str, negative_keywords: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Returns (is_excluded, reason) if any negative keyword is found.
        """
        if not text or not negative_keywords:
            return False, None

        text_lower = text.lower()
        for neg in negative_keywords:
            neg_clean = neg.strip().lower()
            if not neg_clean:
                continue
            pattern = r"\b" + re.escape(neg_clean) + r"\b"
            if re.search(pattern, text_lower) or neg_clean in text_lower:
                return True, f"Negative keyword exclusion: '{neg}'"

        return False, None
