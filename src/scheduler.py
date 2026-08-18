import logging
from collections import deque
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.config import settings
from src.database import (
    get_session,
    get_active_keywords,
    get_unprocessed_mentions,
    get_alert_config,
    mark_reply_sent,
    add_intent_tag,
    update_mention_analysis,
    add_reply,
    get_unsent_replies,
)
from src.database.models import Mention, IntentTag, Reply
from src.pollers.reddit import RedditPoller
from src.pollers.hackernews import HackerNewsPoller
from src.llm import LLMPipeline
from src.alerts import get_email_sender, get_push_sender, get_webhook_sender

logger = logging.getLogger(__name__)

# Ring buffer for recent activity logs (keeps last 200 log messages)
activity_logs = deque(maxlen=200)


class ActivityLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            activity_logs.append({
                "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                "level": record.levelname,
                "name": record.name,
                "message": msg,
            })
        except Exception:
            pass


# Attach handler to root logger
_activity_handler = ActivityLogHandler()
_activity_handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
logging.getLogger().addHandler(_activity_handler)


class PollingJob:
    def __init__(self):
        self.reddit_poller = RedditPoller()
        self.hn_poller = HackerNewsPoller()

    async def run(self) -> Dict[str, int]:
        """Poll all sources for new mentions."""
        with get_session() as session:
            active_kws = get_active_keywords(session)
            keywords = [k.keyword for k in active_kws]
            subreddits = []
            for k in active_kws:
                if k.subreddits:
                    subreddits.extend(k.subreddits)

        if not keywords:
            logger.warning("No active keywords configured")
            return {"reddit": 0, "hackernews": 0, "total": 0}

        logger.info(f"Polling sources for {len(keywords)} active keywords...")

        # Poll Reddit with active subreddits
        reddit_count = self.reddit_poller.poll(keywords, subreddits=subreddits)
        logger.info(f"Reddit poller: {reddit_count} new mentions")

        # Poll Hacker News
        hn_count = await self.hn_poller.poll(keywords)
        logger.info(f"Hacker News poller: {hn_count} new mentions")

        return {
            "reddit": reddit_count,
            "hackernews": hn_count,
            "total": reddit_count + hn_count,
        }


class ProcessingJob:
    def __init__(self):
        self.pipeline = LLMPipeline()

    async def run(self) -> int:
        """Process unprocessed mentions: classify intent, generate replies."""
        with get_session() as session:
            mentions = get_unprocessed_mentions(session, limit=settings.app.max_mentions_per_poll)

        if not mentions:
            logger.debug("No unprocessed mentions found")
            return 0

        logger.info(f"Processing {len(mentions)} unprocessed mentions with AI...")
        processed_count = 0

        for mention in mentions:
            try:
                intent_result, reply_result, analysis_result = await self.pipeline.process_mention(
                    mention_id=mention.id,
                    source=mention.source,
                    title=mention.title or "",
                    content=mention.content or "",
                    subreddit=mention.subreddit or "",
                    post_type=getattr(mention, "post_type", "text") or "text",
                    post_flair=getattr(mention, "post_flair", "") or "",
                    score=mention.score or 0,
                    num_comments=getattr(mention, "num_comments", 0) or 0,
                    upvote_ratio=getattr(mention, "upvote_ratio", 0.0) or 0.0,
                    posted_at=mention.posted_at.isoformat() if mention.posted_at else "",
                )


                with get_session() as session:
                    # Save intent tag
                    if intent_result:
                        add_intent_tag(session, mention.id, intent_result.tag, intent_result.confidence)

                    # Save AI deep analysis (Summary, What it means, Requirements, Urgency, etc.)
                    if analysis_result:
                        update_mention_analysis(session, mention.id, analysis_result.to_dict())

                    # Save reply if generated
                    if reply_result and reply_result.content:
                        add_reply(session, mention.id, reply_result.content, reply_result.model)

                    logger.info(
                        f"Mention #{mention.id} ({mention.source}) -> [{intent_result.tag}] "
                        f"({int(intent_result.confidence * 100)}% conf) | Analyzed"
                    )
                    processed_count += 1

            except Exception as e:
                logger.error(f"Error processing mention #{mention.id}: {e}")

        return processed_count


class AlertJob:
    def __init__(self):
        self.email_sender = get_email_sender()
        self.push_sender = get_push_sender()
        self.webhook_sender = get_webhook_sender()

    async def run(self) -> int:
        """Send alerts for processed mentions with actionable intents."""
        with get_session() as session:
            config = get_alert_config(session)
            if not config:
                logger.debug("No alert config saved, skipping alert job")
                return 0

            # Find unsent replies with actionable intents
            replies = get_unsent_replies(session)
            actionable_tags = set(config.tags_to_alert or ["buy-intent", "pain-point", "competitor-complaint"])
            min_confidence = (config.min_intent_confidence or 70) / 100.0

            mentions_to_alert = []

            for reply in replies:
                mention = session.get(Mention, reply.mention_id)
                if not mention:
                    continue

                from sqlalchemy import select
                intent_tags = session.execute(
                    select(IntentTag).where(IntentTag.mention_id == mention.id)
                ).scalars().all()

                # Check if any intent tag matches alert criteria
                should_alert = False
                for tag in intent_tags:
                    if tag.tag in actionable_tags and (tag.confidence / 100.0) >= min_confidence:
                        should_alert = True
                        break

                if should_alert:
                    mentions_to_alert.append((mention, intent_tags, reply))

            if not mentions_to_alert:
                logger.debug("No pending mentions matching alert criteria")
                return 0

            # Dispatch alerts
            frequency = config.frequency or "immediate"
            dispatched = 0

            if frequency == "immediate":
                for mention, intent_tags, reply in mentions_to_alert:
                    sent = await self._send_alert(mention, intent_tags, reply)
                    if sent:
                        mark_reply_sent(session, reply.id)
                        dispatched += 1
            else:
                # Digest
                if self.email_sender.is_configured():
                    self.email_sender.send_digest(mentions_to_alert)
                if self.push_sender.is_configured():
                    await self.push_sender.send_digest(mentions_to_alert)

                for _, _, reply in mentions_to_alert:
                    mark_reply_sent(session, reply.id)
                    dispatched += 1

                logger.info(f"Dispatched {frequency} digest for {len(mentions_to_alert)} mentions")

            return dispatched

    async def _send_alert(self, mention: Mention, intent_tags: List[IntentTag], reply: Reply) -> bool:
        """Send individual alert via email, push, and webhook."""
        sent = False
        if self.email_sender.is_configured():
            sent |= self.email_sender.send_immediate_alert(mention, intent_tags, reply)
        if self.push_sender.is_configured():
            sent |= await self.push_sender.send_immediate_alert(mention, intent_tags, reply)
        if self.webhook_sender.is_configured():
            sent |= await self.webhook_sender.send_immediate_alert(mention, intent_tags, reply)
        return sent


class SchedulerManager:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.polling_job = PollingJob()
        self.processing_job = ProcessingJob()
        self.alert_job = AlertJob()
        self.is_running = False
        self.last_poll_time: Optional[str] = None
        self.last_process_time: Optional[str] = None
        self.last_alert_time: Optional[str] = None
        self.stats = {
            "polls_count": 0,
            "processes_count": 0,
            "alerts_sent": 0,
            "mentions_discovered": 0,
        }

    def start(self):
        """Configure and start the scheduler."""
        if self.is_running:
            return

        self.scheduler.add_job(
            self._wrapped_poll,
            IntervalTrigger(minutes=settings.app.poll_interval_minutes),
            id="poll_sources",
            name="Poll Reddit and HN",
            replace_existing=True,
        )

        self.scheduler.add_job(
            self._wrapped_process,
            IntervalTrigger(minutes=settings.app.process_interval_minutes),
            id="process_mentions",
            name="Process mentions (classify + reply)",
            replace_existing=True,
        )

        freq = settings.alerts.digest_frequency
        if freq == "immediate":
            self.scheduler.add_job(
                self._wrapped_alert,
                IntervalTrigger(minutes=1),
                id="send_alerts",
                name="Send immediate alerts",
                replace_existing=True,
            )
        elif freq == "hourly":
            self.scheduler.add_job(
                self._wrapped_alert,
                IntervalTrigger(hours=1),
                id="send_alerts",
                name="Send hourly digest",
                replace_existing=True,
            )
        elif freq == "daily":
            self.scheduler.add_job(
                self._wrapped_alert,
                IntervalTrigger(days=1),
                id="send_alerts",
                name="Send daily digest",
                replace_existing=True,
            )

        self.scheduler.start()
        self.is_running = True
        logger.info("ParseStream Scheduler started successfully")

    def stop(self):
        if self.is_running:
            self.scheduler.shutdown(wait=False)
            self.scheduler = AsyncIOScheduler()
            self.is_running = False
            logger.info("ParseStream Scheduler stopped")

    async def _wrapped_poll(self):
        self.last_poll_time = datetime.now(timezone.utc).isoformat()
        res = await self.polling_job.run()
        self.stats["polls_count"] += 1
        self.stats["mentions_discovered"] += res.get("total", 0)
        return res

    async def _wrapped_process(self):
        self.last_process_time = datetime.now(timezone.utc).isoformat()
        count = await self.processing_job.run()
        self.stats["processes_count"] += 1
        return count

    async def _wrapped_alert(self):
        self.last_alert_time = datetime.now(timezone.utc).isoformat()
        sent = await self.alert_job.run()
        self.stats["alerts_sent"] += sent
        return sent

    async def trigger_poll(self) -> Dict[str, Any]:
        return await self._wrapped_poll()

    async def trigger_process(self) -> int:
        return await self._wrapped_process()

    async def trigger_alert(self) -> int:
        return await self._wrapped_alert()

    async def trigger_cycle(self) -> Dict[str, Any]:
        poll_res = await self.trigger_poll()
        proc_count = await self.trigger_process()
        alert_count = await self.trigger_alert()
        return {
            "polling": poll_res,
            "processed": proc_count,
            "alerts_sent": alert_count,
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running,
            "poll_interval_minutes": settings.app.poll_interval_minutes,
            "process_interval_minutes": settings.app.process_interval_minutes,
            "alert_frequency": settings.alerts.digest_frequency,
            "last_poll_time": self.last_poll_time,
            "last_process_time": self.last_process_time,
            "last_alert_time": self.last_alert_time,
            "stats": self.stats,
        }


# Singleton manager
scheduler_manager = SchedulerManager()


def setup_scheduler():
    return scheduler_manager.scheduler


async def run_manual_poll():
    return await scheduler_manager.trigger_poll()


async def run_manual_process():
    return await scheduler_manager.trigger_process()


async def run_manual_alert():
    return await scheduler_manager.trigger_alert()