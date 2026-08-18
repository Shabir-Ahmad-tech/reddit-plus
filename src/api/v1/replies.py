"""
Reply Generation and Critic Router.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any

from src.database.session import get_db
from src.database.repositories.reply_repository import ReplyRepository
from src.database.repositories.match_repository import MatchRepository
from src.database.repositories.post_repository import PostRepository
from src.api.schemas.models import (
    ReplyGenerateRequest,
    ReplyRegenerateRequest,
    ReplyUpdateRequest,
    ReplyCriticRequest,
)
from src.replies import ReplyGenerator, ReplyCritic, STRATEGY_DESCRIPTIONS

router = APIRouter(prefix="/replies", tags=["Replies"])


@router.get("/strategies")
def list_strategies():
    """List available reply generation strategies."""
    return STRATEGY_DESCRIPTIONS


@router.post("/generate")
async def generate_reply_endpoint(req: ReplyGenerateRequest, db: Session = Depends(get_db)):
    """Generate a draft reply for a post or match."""
    post_repo = PostRepository(db)
    reply_repo = ReplyRepository(db)
    match_repo = MatchRepository(db)

    title = req.title or ""
    content = req.content or ""
    subreddit = req.subreddit or "all"
    intent_tag = req.intent_tag or "question"
    post_id = req.post_id
    match_id = req.match_id

    if match_id:
        match = match_repo.get_by_id(match_id)
        if match and match.post:
            post_id = match.post.id
            title = match.post.title
            content = match.post.body or ""
            subreddit = match.post.subreddit
            if match.post.analysis:
                intent_tag = match.post.analysis.intent_tag

    if not title and not content:
        raise HTTPException(status_code=400, detail="Title or content is required")

    gen = ReplyGenerator()
    result = await gen.generate_reply(
        title=title,
        content=content,
        subreddit=subreddit,
        intent_tag=intent_tag,
        strategy=req.strategy,
        recommended_angle=req.recommended_angle,
        product_context=req.product_context,
    )

    draft = None
    if match_id:
        draft = reply_repo.create_draft(
            match_id=match_id,
            post_id=post_id,
            content=result.content,
            strategy=result.strategy,
            model_used=result.model_used,
            critic_scorecard=result.critic.to_dict(),
            promotion_risk=result.critic.promotion_risk,
            is_safe=result.critic.is_safe,
        )

    return {
        "id": draft.id if draft else None,
        "content": result.content,
        "strategy": result.strategy,
        "model_used": result.model_used,
        "is_fallback": result.is_fallback,
        "critic": result.critic.to_dict(),
    }


@router.post("/{reply_id}/regenerate")
async def regenerate_reply_endpoint(
    reply_id: int,
    req: ReplyRegenerateRequest,
    db: Session = Depends(get_db),
):
    """Regenerate an existing reply draft with a new strategy."""
    reply_repo = ReplyRepository(db)
    match_repo = MatchRepository(db)

    reply = reply_repo.get_by_id(reply_id)
    if not reply:
        raise HTTPException(status_code=404, detail="Reply draft not found")

    match = match_repo.get_by_id(reply.match_id)
    if not match or not match.post:
        raise HTTPException(status_code=404, detail="Associated post not found")

    post = match.post
    intent_tag = post.analysis.intent_tag if post.analysis else "question"

    gen = ReplyGenerator()
    result = await gen.generate_reply(
        title=post.title,
        content=post.body or "",
        subreddit=post.subreddit,
        intent_tag=intent_tag,
        strategy=req.strategy,
        recommended_angle=req.recommended_angle or (post.analysis.recommended_angle if post.analysis else None),
        product_context=req.product_context,
    )

    reply.content = result.content
    reply.strategy = result.strategy
    reply.model_used = result.model_used
    reply.critic_scorecard = result.critic.to_dict()
    reply.promotion_risk = result.critic.promotion_risk
    reply.is_safe = result.critic.is_safe
    db.commit()

    return {
        "id": reply.id,
        "content": reply.content,
        "strategy": reply.strategy,
        "model_used": reply.model_used,
        "critic": reply.critic_scorecard,
        "status": reply.status,
    }


@router.patch("/{reply_id}")
def update_reply(reply_id: int, req: ReplyUpdateRequest, db: Session = Depends(get_db)):
    """Update reply content or mark as sent/approved."""
    reply_repo = ReplyRepository(db)
    reply = reply_repo.get_by_id(reply_id)
    if not reply:
        raise HTTPException(status_code=404, detail="Reply draft not found")

    if req.content is not None:
        reply.content = req.content
    if req.status is not None:
        reply = reply_repo.mark_status(reply_id, req.status)

    db.commit()
    return {
        "id": reply.id,
        "content": reply.content,
        "status": reply.status,
        "sent_at": reply.sent_at.isoformat() if reply.sent_at else None,
    }


@router.post("/critic")
async def run_critic(req: ReplyCriticRequest):
    """Run standalone Reply Critic on an arbitrary text."""
    critic = ReplyCritic()
    eval_result = await critic.evaluate(
        reply=req.reply,
        title=req.title,
        content=req.content,
        subreddit=req.subreddit,
    )
    return eval_result.to_dict()
