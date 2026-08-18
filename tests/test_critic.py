"""
Unit Tests for Reply Critic & Safety.
"""

from src.replies.critic import ReplyCritic


def test_heuristic_critic_on_clean_reply():
    critic = ReplyCritic()
    eval_result = critic._heuristic_evaluation("You can solve this by adding a custom middleware in FastAPI to handle CORS headers before the router handles the request.")
    assert eval_result.is_safe is True
    assert eval_result.promotion_risk < 50
    assert eval_result.verdict == "APPROVED"


def test_heuristic_critic_on_promotional_reply():
    critic = ReplyCritic()
    eval_result = critic._heuristic_evaluation("You must check out my game-changer tool at http://mysaas.com! It is the best on the market with a huge discount.")
    assert eval_result.promotion_risk >= 70
    assert eval_result.is_safe is False
    assert eval_result.verdict == "REVISE"
