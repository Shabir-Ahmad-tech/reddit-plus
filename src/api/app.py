import os
import io
import csv
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from src.config import settings
from src.database import (
    init_db,
    get_session,
    get_mention_by_id,
    update_mention_analysis,
    get_mentions_filtered,
    delete_mention,
    get_dashboard_stats,
    add_keyword,
    get_all_keywords,
    update_keyword_active,
    delete_keyword_by_id,
    update_reply_content,
    mark_reply_sent,
    get_alert_config,
    upsert_alert_config,
    semantic_search,
    embed_text,
    get_all_mentions_for_reclassify,
    add_intent_tag,
)

from src.database.models import Mention, IntentTag, Reply
from src.pollers.reddit import RedditPoller
from src.pollers.hackernews import HackerNewsPoller
from src.llm import (
    get_ollama_client,
    get_llm_client,
    OpenCodeZenClient,
    classify_intent,
    generate_reply,
    analyze_post,
)
from src.scheduler import scheduler_manager, activity_logs
from src.alerts import get_email_sender, get_push_sender, get_webhook_sender

logger = logging.getLogger(__name__)

# Base directory
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


def create_app() -> FastAPI:
    app = FastAPI(
        title="ParseStream Free",
        description="Free, self-hosted social monitoring with AI intent classification and Web UI",
        version="1.0.0",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def on_startup():
        init_db()
        # Optionally auto-start scheduler
        scheduler_manager.start()

    # --- Pydantic Schemas ---

    class KeywordCreate(BaseModel):
        keyword: str = Field(..., min_length=1)
        sources: List[str] = Field(default=["reddit", "hackernews"])
        subreddits: Optional[List[str]] = None
        min_score: int = Field(default=1, ge=0)

    class KeywordToggle(BaseModel):
        active: bool

    class ReplyUpdate(BaseModel):
        content: str
        sent: Optional[bool] = None

    class ReplyRegenerate(BaseModel):
        tone: str = Field(default="casual")
        custom_instructions: Optional[str] = None

    class AlertConfigUpdate(BaseModel):
        email: Optional[str] = None
        ntfy_topic: Optional[str] = None
        webhook_url: Optional[str] = None
        min_intent_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
        tags_to_alert: List[str] = Field(default=["buy-intent", "pain-point", "competitor-complaint"])
        frequency: str = Field(default="hourly")

    class LLMConfigUpdate(BaseModel):
        provider: Optional[str] = "opencode_zen"
        model: Optional[str] = "deepseek-v4-flash-free"
        api_key: Optional[str] = None
        base_url: Optional[str] = None

    class TestKeywordRequest(BaseModel):
        keyword: str
        source: str = "all"
        subreddit: Optional[str] = "all"
        limit: int = 10

    class TestAIRequest(BaseModel):
        text: str

    class TestAIReplyRequest(BaseModel):
        source: str = "reddit"
        title: str = ""
        content: str
        intent_tag: str = "buy-intent"
        tone: str = "casual"

    class TestAlertRequest(BaseModel):
        email: bool = True
        push: bool = True
        ntfy_topic: Optional[str] = None
        email_to: Optional[str] = None
        webhook_url: Optional[str] = None

    # --- Serializer Helper ---

    def serialize_mention(m: Mention) -> Dict[str, Any]:
        tags = [{"id": t.id, "tag": t.tag, "confidence": t.confidence} for t in (m.intent_tags or [])]
        replies = [
            {"id": r.id, "content": r.content, "model": r.model, "sent": bool(r.sent), "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in (m.replies or [])
        ]
        return {
            "id": m.id,
            "source": m.source,
            "source_id": m.source_id,
            "url": m.url,
            "title": m.title,
            "content": m.content,
            "author": m.author,
            "subreddit": m.subreddit,
            # Reddit-native signals
            "score": m.score,
            "num_comments": getattr(m, "num_comments", 0) or 0,
            "upvote_ratio": getattr(m, "upvote_ratio", 0.0) or 0.0,
            "post_flair": getattr(m, "post_flair", None),
            "post_type": getattr(m, "post_type", "text") or "text",
            "thumbnail_url": getattr(m, "thumbnail_url", None),
            "awards_count": getattr(m, "awards_count", 0) or 0,
            # Timestamps
            "posted_at": m.posted_at.isoformat() if m.posted_at else None,
            "fetched_at": m.fetched_at.isoformat() if m.fetched_at else None,
            # AI data
            "intent_tags": tags,
            "replies": replies,
            "primary_tag": tags[0]["tag"] if tags else None,
            "primary_confidence": tags[0]["confidence"] if tags else 0,
            "latest_reply": replies[0] if replies else None,
            "ai_analysis": m.ai_analysis,
        }


    # --- Endpoints ---

    @app.get("/api/stats")
    def get_stats():
        """Retrieve aggregated dashboard metrics."""
        with get_session() as session:
            stats = get_dashboard_stats(session)
            scheduler_status = scheduler_manager.get_status()
            stats["scheduler"] = scheduler_status
            return stats

    @app.get("/api/mentions")
    def list_mentions(
        source: Optional[str] = Query(None),
        tag: Optional[str] = Query(None),
        query: Optional[str] = Query(None),
        min_confidence: Optional[float] = Query(None),
        has_reply: Optional[bool] = Query(None),
        is_sent: Optional[bool] = Query(None),
        hours: Optional[int] = Query(None),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ):
        """Query mentions with rich filters and pagination."""
        with get_session() as session:
            mentions, total = get_mentions_filtered(
                session=session,
                source=source,
                tag=tag,
                query=query,
                min_confidence=min_confidence,
                has_reply=has_reply,
                is_sent=is_sent,
                hours=hours,
                limit=limit,
                offset=offset,
            )
            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "items": [serialize_mention(m) for m in mentions],
            }

    @app.get("/api/mentions/{mention_id}")
    def get_mention(mention_id: int):
        """Get single mention details."""
        with get_session() as session:
            m = get_mention_by_id(session, mention_id)
            if not m:
                raise HTTPException(status_code=404, detail="Mention not found")
            return serialize_mention(m)

    @app.delete("/api/mentions/{mention_id}")
    def remove_mention(mention_id: int):
        """Delete a mention."""
        with get_session() as session:
            success = delete_mention(session, mention_id)
            if not success:
                raise HTTPException(status_code=404, detail="Mention not found")
            return {"success": True, "message": f"Mention {mention_id} deleted"}

    @app.post("/api/mentions/{mention_id}/analyze")
    async def analyze_mention_endpoint(mention_id: int):
        """Trigger or regenerate deep AI analysis for a Reddit post on-demand."""
        with get_session() as session:
            m = get_mention_by_id(session, mention_id)
            if not m:
                raise HTTPException(status_code=404, detail="Mention not found")
            source = m.source
            title = m.title or ""
            content = m.content or ""
            subreddit = m.subreddit or ""
            post_type = getattr(m, "post_type", "text") or "text"
            post_flair = getattr(m, "post_flair", "") or ""
            score = m.score or 0
            num_comments = getattr(m, "num_comments", 0) or 0
            upvote_ratio = getattr(m, "upvote_ratio", 0.0) or 0.0
            posted_at = m.posted_at.isoformat() if m.posted_at else ""

        analysis_res = await analyze_post(
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
        analysis_dict = analysis_res.to_dict()

        with get_session() as session:
            update_mention_analysis(session, mention_id, analysis_dict)
            return {
                "success": True,
                "analysis": analysis_dict,
            }


    @app.post("/api/mentions/{mention_id}/regenerate-reply")
    async def regenerate_reply_for_mention(mention_id: int, req: ReplyRegenerate):
        """Regenerate AI reply with requested tone."""
        with get_session() as session:
            m = get_mention_by_id(session, mention_id)
            if not m:
                raise HTTPException(status_code=404, detail="Mention not found")

            primary_tag = m.intent_tags[0].tag if m.intent_tags else "buy-intent"
            source = m.source
            title = m.title or ""
            content = m.content or ""

        reply_res = await generate_reply(
            source=source,
            title=title,
            content=content,
            intent_tag=primary_tag,
            tone=req.tone,
        )

        with get_session() as session:
            from src.database import add_reply
            reply_obj = add_reply(session, mention_id, reply_res.content, reply_res.model)
            return {
                "success": True,
                "reply": {
                    "id": reply_obj.id,
                    "content": reply_obj.content,
                    "model": reply_obj.model,
                    "sent": bool(reply_obj.sent),
                    "is_fallback": reply_res.is_fallback,
                }
            }

    @app.put("/api/mentions/{mention_id}/reply")
    def update_mention_reply(mention_id: int, req: ReplyUpdate):
        """Edit suggested reply or toggle sent flag."""
        with get_session() as session:
            m = get_mention_by_id(session, mention_id)
            if not m or not m.replies:
                raise HTTPException(status_code=404, detail="Mention or reply not found")

            reply = m.replies[0]
            if req.content:
                reply.content = req.content
            if req.sent is not None:
                reply.sent = 1 if req.sent else 0
            return {"success": True, "message": "Reply updated"}

    # --- Keywords Management ---

    @app.get("/api/keywords")
    def list_keywords():
        with get_session() as session:
            keywords = get_all_keywords(session)
            return [
                {
                    "id": k.id,
                    "keyword": k.keyword,
                    "sources": k.sources or [],
                    "subreddits": k.subreddits or [],
                    "min_score": k.min_score,
                    "active": bool(k.active),
                    "created_at": k.created_at.isoformat() if k.created_at else None,
                }
                for k in keywords
            ]

    @app.post("/api/keywords")
    def create_keyword(kw: KeywordCreate):
        with get_session() as session:
            item = add_keyword(
                session=session,
                keyword=kw.keyword,
                sources=kw.sources,
                subreddits=kw.subreddits,
                min_score=kw.min_score,
            )
            return {
                "id": item.id,
                "keyword": item.keyword,
                "sources": item.sources,
                "subreddits": item.subreddits,
                "min_score": item.min_score,
                "active": bool(item.active),
            }

    @app.put("/api/keywords/{keyword_id}/toggle")
    def toggle_keyword(keyword_id: int, req: KeywordToggle):
        with get_session() as session:
            kw = update_keyword_active(session, keyword_id, req.active)
            if not kw:
                raise HTTPException(status_code=404, detail="Keyword not found")
            return {"success": True, "active": bool(kw.active)}

    @app.delete("/api/keywords/{keyword_id}")
    def remove_keyword(keyword_id: int):
        with get_session() as session:
            success = delete_keyword_by_id(session, keyword_id)
            if not success:
                raise HTTPException(status_code=404, detail="Keyword not found")
            return {"success": True, "message": "Keyword deleted"}

    @app.post("/api/keywords/test")
    @app.post("/api/keywords/test-search")
    async def test_keyword_live(req: TestKeywordRequest):
        """Test search keyword live across Reddit and HN APIs."""
        results = []
        if req.source in ("all", "hackernews"):
            hn = HackerNewsPoller()
            hn_items = await hn.search_live(req.keyword, limit=req.limit)
            results.extend(hn_items)
            await hn.close()

        if req.source in ("all", "reddit"):
            reddit = RedditPoller()
            reddit_items = await reddit.search_live(
                keyword=req.keyword,
                subreddit=req.subreddit or "all",
                limit=req.limit,
            )
            results.extend(reddit_items)
            await reddit.close()

        return {"count": len(results), "items": results}

    # --- Configuration & Integrations ---

    @app.get("/api/config")
    def get_configuration():
        with get_session() as session:
            db_alert = get_alert_config(session)
            return {
                "app": {
                    "poll_interval_minutes": settings.app.poll_interval_minutes,
                    "process_interval_minutes": settings.app.process_interval_minutes,
                    "max_mentions_per_poll": settings.app.max_mentions_per_poll,
                    "database_path": settings.app.database_path,
                },
                "reddit": {
                    "client_id": settings.reddit.client_id,
                    "client_secret": "***" if settings.reddit.client_secret else "",
                    "user_agent": settings.reddit.user_agent,
                    "subreddits": settings.reddit.subreddits,
                },
                "hackernews": {
                    "enabled": settings.hackernews.enabled,
                    "base_url": settings.hackernews.base_url,
                },
                "llm": {
                    "provider": getattr(settings.llm, "provider", "opencode_zen"),
                    "model": getattr(settings.llm, "model", "deepseek-v4-flash-free"),
                    "opencode_zen": {
                        "enabled": bool(getattr(settings.llm.opencode_zen, "enabled", True)),
                        "base_url": getattr(settings.llm.opencode_zen, "base_url", "https://opencode.ai/zen/v1"),
                        "api_key_configured": bool(getattr(settings.llm.opencode_zen, "api_key", "")),
                        "api_key_preview": (getattr(settings.llm.opencode_zen, "api_key", "")[:8] + "..." + getattr(settings.llm.opencode_zen, "api_key", "")[-4:]) if getattr(settings.llm.opencode_zen, "api_key", "") else "",
                        "model": getattr(settings.llm.opencode_zen, "model", "deepseek-v4-flash-free"),
                    },
                    "ollama": {
                        "host": settings.ollama.host,
                        "model": settings.ollama.model,
                    },
                },
                "ollama": {
                    "host": settings.ollama.host,
                    "model": settings.ollama.model,
                    "timeout_seconds": settings.ollama.timeout_seconds,
                    "intent_prompt": settings.ollama.intent_prompt,
                    "reply_prompt": settings.ollama.reply_prompt,
                },
                "alerts": {
                    "email": db_alert.email if db_alert else settings.alerts.sendgrid.to_email,
                    "sendgrid_configured": bool(settings.alerts.sendgrid.api_key and not settings.alerts.sendgrid.api_key.startswith("${")),
                    "ntfy_topic": db_alert.ntfy_topic if db_alert else settings.alerts.ntfy.topic,
                    "min_confidence": (db_alert.min_intent_confidence / 100.0) if db_alert else settings.alerts.min_confidence,
                    "tags_to_alert": db_alert.tags_to_alert if db_alert else settings.alerts.alert_tags,
                    "frequency": db_alert.frequency if db_alert else settings.alerts.digest_frequency,
                },
            }

    @app.put("/api/config/alerts")
    def update_alert_config_endpoint(req: AlertConfigUpdate):
        """Save alert preferences to database and runtime settings."""
        with get_session() as session:
            cfg = upsert_alert_config(
                session=session,
                email=req.email,
                ntfy_topic=req.ntfy_topic,
                min_intent_confidence=req.min_intent_confidence,
                tags_to_alert=req.tags_to_alert,
                frequency=req.frequency,
            )
            # Also update in-memory settings
            if req.email is not None:
                settings.alerts.sendgrid.to_email = req.email
            if req.ntfy_topic is not None:
                settings.alerts.ntfy.topic = req.ntfy_topic
            if req.min_intent_confidence is not None:
                settings.alerts.min_confidence = req.min_intent_confidence
            if req.tags_to_alert is not None:
                settings.alerts.alert_tags = req.tags_to_alert
            if req.frequency is not None:
                settings.alerts.digest_frequency = req.frequency

            return {
                "success": True,
                "message": "Alert configuration saved successfully",
                "alerts": {
                    "email": cfg.email,
                    "ntfy_topic": cfg.ntfy_topic,
                    "min_confidence": cfg.min_intent_confidence / 100.0,
                    "tags_to_alert": cfg.tags_to_alert,
                    "frequency": cfg.frequency,
                },
            }

    @app.put("/api/config/llm")
    def update_llm_config(req: LLMConfigUpdate):
        if req.provider:
            settings.llm.provider = req.provider
        if req.model:
            settings.llm.model = req.model
            if req.provider == "opencode_zen":
                settings.llm.opencode_zen.model = req.model
            elif req.provider == "ollama":
                settings.llm.ollama.model = req.model
                settings.ollama.model = req.model
        if req.api_key:
            settings.llm.opencode_zen.api_key = req.api_key
        if req.base_url:
            settings.llm.opencode_zen.base_url = req.base_url

        return {
            "success": True,
            "message": f"LLM configuration updated to provider: {settings.llm.provider}, model: {settings.llm.model}",
        }

    @app.get("/api/config/zen-models")
    async def get_zen_models():
        """Retrieve available models from OpenCode Zen."""
        zen = OpenCodeZenClient()
        models = await zen.list_models()
        await zen.close()
        # Separate free models
        free_models = [m for m in models if "free" in m.lower()]
        return {"models": models, "free_models": free_models, "count": len(models)}

    @app.post("/api/config/test-llm")
    async def test_llm_endpoint():
        """Test primary LLM provider connection (OpenCode Zen or Ollama)."""
        client = get_llm_client()
        status_info = await client.health_check()
        sample_response = None
        healthy = False

        active_provider = client.active_provider
        if active_provider == "opencode_zen":
            healthy = status_info["opencode_zen"]["healthy"]
        else:
            healthy = status_info["ollama"]["healthy"]

        if healthy:
            try:
                sample_response = await client.generate("Say 'ParseStream LLM connection is healthy!' in 5 words.")
            except Exception as e:
                sample_response = f"Generated error: {e}"

        return {
            "healthy": healthy,
            "provider": active_provider,
            "model": client.active_model,
            "sample_response": sample_response,
            "details": status_info,
        }

    @app.post("/api/config/test-ollama")
    async def test_ollama_endpoint():
        return await test_llm_endpoint()

    @app.post("/api/config/test-reddit")
    def test_reddit_endpoint():
        reddit = RedditPoller()
        connected = reddit.test_connection()
        return {"connected": connected, "subreddits": settings.reddit.subreddits}

    @app.post("/api/config/test-hn")
    async def test_hn_endpoint():
        hn = HackerNewsPoller()
        connected = await hn.test_connection()
        await hn.close()
        return {"connected": connected}

    @app.post("/api/config/test-alert")
    async def trigger_test_alert(req: TestAlertRequest = TestAlertRequest()):
        mock_mention = Mention(
            id=9999,
            source="reddit",
            source_id="test_id",
            url="https://reddit.com/r/saas/comments/test",
            title="[Test Alert] Looking for a great social monitoring tool",
            content="This is a test notification dispatched from ParseStream Free to verify your alert channels are active.",
            author="demo_user",
            subreddit="saas",
            score=25,
            posted_at=datetime.now(timezone.utc),
        )
        mock_tags = [IntentTag(id=1, mention_id=9999, tag="buy-intent", confidence=95)]
        mock_reply = Reply(id=1, mention_id=9999, content="Here is an AI-generated suggested response for this mention.", model="test")

        results = {}

        if req.push:
            sender = get_push_sender()
            topic = (req.ntfy_topic or sender.get_topic()).strip()
            results["push_configured"] = bool(topic)
            results["push_topic"] = topic
            if topic:
                sent = await sender.send_immediate_alert(mock_mention, mock_tags, mock_reply, custom_topic=topic)
                results["push_sent"] = sent
            else:
                results["push_sent"] = False
                results["push_error"] = "No ntfy topic specified. Enter a topic under Push Notifications."

        if req.email:
            sender = get_email_sender()
            results["email_configured"] = sender.is_configured()
            results["email_sent"] = sender.send_immediate_alert(mock_mention, mock_tags, mock_reply) if sender.is_configured() else False
            if not sender.is_configured():
                results["email_error"] = "SendGrid API key not configured in .env"

        if req.webhook_url:
            sender = get_webhook_sender(req.webhook_url)
            results["webhook_sent"] = await sender.send_immediate_alert(mock_mention, mock_tags, mock_reply)
            await sender.close()

        return {"success": True, "details": results}

    # --- AI Playground ---

    @app.post("/api/ai/test-intent")
    async def test_intent_playground(req: TestAIRequest):
        res = await classify_intent(req.text)
        return {
            "tag": res.tag,
            "confidence": res.confidence,
            "confidence_percent": int(res.confidence * 100),
            "is_fallback": res.is_fallback,
        }

    @app.post("/api/ai/test-reply")
    async def test_reply_playground(req: TestAIReplyRequest):
        res = await generate_reply(
            source=req.source,
            title=req.title,
            content=req.content,
            intent_tag=req.intent_tag,
            tone=req.tone,
        )
        return {
            "reply": res.content,
            "model": res.model,
            "is_fallback": res.is_fallback,
        }

    @app.post("/api/ai/test-analyze")
    async def test_analyze_playground(req: TestAIReplyRequest):
        res = await analyze_post(
            source=req.source,
            title=req.title,
            content=req.content,
        )
        return res.to_dict()

    # --- Scheduler Controls ---

    @app.get("/api/scheduler/status")
    def get_scheduler_status():
        return scheduler_manager.get_status()

    @app.post("/api/scheduler/start")
    def start_scheduler():
        scheduler_manager.start()
        return {"success": True, "status": scheduler_manager.get_status()}

    @app.post("/api/scheduler/stop")
    def stop_scheduler():
        scheduler_manager.stop()
        return {"success": True, "status": scheduler_manager.get_status()}

    @app.post("/api/scheduler/trigger-poll")
    async def trigger_poll_now():
        res = await scheduler_manager.trigger_poll()
        return {"success": True, "result": res}

    @app.post("/api/scheduler/trigger-process")
    async def trigger_process_now():
        count = await scheduler_manager.trigger_process()
        return {"success": True, "processed_count": count}

    @app.post("/api/scheduler/trigger-alert")
    async def trigger_alert_now():
        sent = await scheduler_manager.trigger_alert()
        return {"success": True, "alerts_sent": sent}

    @app.post("/api/scheduler/trigger-cycle")
    async def trigger_full_cycle():
        res = await scheduler_manager.trigger_cycle()
        return {"success": True, "cycle_results": res}

    @app.post("/api/scheduler/reclassify")
    async def reclassify_all_mentions():
        """Force re-classify ALL existing mentions with fresh LLM calls.
        This overwrites stale fallback (60%) confidence scores.
        """
        from src.llm import classify_intent as _classify_intent

        with get_session() as session:
            mentions = get_all_mentions_for_reclassify(session, limit=200)

        updated = 0
        errors = 0
        for mention in mentions:
            try:
                content = mention.content or mention.title or ""
                if not content.strip():
                    continue
                result = await _classify_intent(content)
                with get_session() as session:
                    add_intent_tag(session, mention.id, result.tag, result.confidence)
                updated += 1
            except Exception as e:
                logger.warning(f"Reclassify error for mention #{mention.id}: {e}")
                errors += 1

        return {
            "success": True,
            "updated": updated,
            "errors": errors,
            "message": f"Re-classified {updated} posts with fresh AI confidence scores",
        }

    @app.post("/api/mentions/{mention_id}/reclassify")
    async def reclassify_single_mention(mention_id: int):
        """Re-classify a single mention with a fresh LLM call."""
        from src.llm import classify_intent as _classify_intent
        with get_session() as session:
            m = get_mention_by_id(session, mention_id)
            if not m:
                raise HTTPException(status_code=404, detail="Mention not found")
            content = m.content or m.title or ""

        result = await _classify_intent(content)
        with get_session() as session:
            add_intent_tag(session, mention_id, result.tag, result.confidence)
        return {
            "success": True,
            "tag": result.tag,
            "confidence": result.confidence,
            "confidence_percent": int(result.confidence * 100),
            "is_fallback": result.is_fallback,
        }

    @app.get("/api/logs")
    def get_logs(limit: int = 100):
        items = list(activity_logs)
        return items[-limit:]

    # --- Export Data ---

    @app.get("/api/export")
    def export_data(format: str = Query("json", enum=["json", "csv"])):
        with get_session() as session:
            mentions, _ = get_mentions_filtered(session, limit=1000)
            data = [serialize_mention(m) for m in mentions]

        if format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["ID", "Source", "Title", "URL", "Author", "Score", "Posted At", "Intent Tag", "Confidence", "Reply", "Reply Sent"])
            for m in data:
                writer.writerow([
                    m["id"],
                    m["source"],
                    m["title"],
                    m["url"],
                    m["author"],
                    m["score"],
                    m["posted_at"],
                    m["primary_tag"] or "",
                    m["primary_confidence"] or 0,
                    m["latest_reply"]["content"] if m.get("latest_reply") else "",
                    m["latest_reply"]["sent"] if m.get("latest_reply") else False,
                ])
            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=parsestream_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"},
            )
        else:
            return JSONResponse(
                content=data,
                headers={"Content-Disposition": f"attachment; filename=parsestream_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"},
            )

    # --- Static & SPA Frontend ---

    index_html_path = STATIC_DIR / "index.html"

    @app.get("/", response_class=HTMLResponse)
    async def serve_index():
        if index_html_path.exists():
            return FileResponse(index_html_path)
        return HTMLResponse("<h1>ParseStream Free</h1><p>UI is initializing...</p>")

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app


app = create_app()
