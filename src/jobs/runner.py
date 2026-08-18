"""
Background Job Runner for Reddit Plus v2.
Coordinates continuous ingestion, matching, AI analysis, reply generation, and notification delivery.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import deque

from src.config import settings
from src.database.session import get_session
from src.database.models import MonitoringRule, RedditPost, Match, Analysis
from src.database.repositories.post_repository import PostRepository
from src.database.repositories.comment_repository import CommentRepository
from src.database.repositories.rule_repository import RuleRepository
from src.database.repositories.match_repository import MatchRepository
from src.database.repositories.analysis_repository import AnalysisRepository
from src.database.repositories.reply_repository import ReplyRepository
from src.database.repositories.notification_repository import NotificationRepository

from src.reddit import RedditClient, SubmissionFetcher, CommentFetcher
from src.matching import MatchingEngine
from src.intelligence import IntentClassifier, PostAnalyzer, OpportunityScorer
from src.replies import ReplyGenerator
from src.alerts.push import get_push_sender
from src.alerts.email import get_email_sender
from src.alerts.webhook import get_webhook_sender

logger = logging.getLogger(__name__)

# In-memory activity ring buffer
activity_logs: deque = deque(maxlen=200)


def log_event(message: str, level: str = "info", details: Optional[Dict[str, Any]] = None):
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "message": message,
        "details": details or {},
    }
    activity_logs.append(entry)
    if level == "error":
        logger.error(message)
    elif level == "warning":
        logger.warning(message)
    else:
        logger.info(message)


class JobRunner:
    def __init__(self):
        self.reddit_client = RedditClient()
        self.submission_fetcher = SubmissionFetcher(self.reddit_client)
        self.comment_fetcher = CommentFetcher(self.reddit_client)

        self.matching_engine = MatchingEngine()
        self.intent_classifier = IntentClassifier()
        self.post_analyzer = PostAnalyzer()
        self.reply_generator = ReplyGenerator()

        self.push_sender = get_push_sender()
        self.email_sender = get_email_sender()
        self.webhook_sender = get_webhook_sender()

        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self.last_run_time: Optional[datetime] = None
        self.stats = {
            "posts_ingested": 0,
            "comments_ingested": 0,
            "matches_found": 0,
            "analyses_completed": 0,
            "replies_drafted": 0,
            "alerts_sent": 0,
        }

    async def start(self):
        """Start continuous background processing loop."""
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._run_loop())
        log_event("Reddit Plus v2 Background Job Runner started", "info")

    async def stop(self):
        """Stop continuous background processing loop."""
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
        log_event("Reddit Plus v2 Background Job Runner stopped", "info")

    async def _run_loop(self):
        while self.is_running:
            try:
                await self.run_full_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log_event(f"Error in job cycle: {e}", "error")

            # Sleep between cycles (default 10 mins)
            poll_interval = settings.reddit.poll_interval_seconds or 600
            await asyncio.sleep(poll_interval)

    async def run_full_cycle(self) -> Dict[str, Any]:
        """Execute a complete ingestion -> match -> analyze -> reply -> alert cycle."""
        self.last_run_time = datetime.utcnow()
        log_event("Starting full Reddit Plus intelligence cycle...", "info")

        results = {
            "posts_ingested": 0,
            "matches_found": 0,
            "analyses_completed": 0,
            "replies_drafted": 0,
            "alerts_sent": 0,
        }

        # Step 1: Ingestion
        ingested = await self.job_poll_subreddits()
        results["posts_ingested"] = ingested
        self.stats["posts_ingested"] += ingested

        # Step 2: Matching
        matches = await self.job_match_posts()
        results["matches_found"] = matches
        self.stats["matches_found"] += matches

        # Step 3: Analysis & Opportunity Scoring
        analyzed = await self.job_analyze_matches()
        results["analyses_completed"] = analyzed
        self.stats["analyses_completed"] += analyzed

        # Step 4: Reply Drafting
        replies = await self.job_draft_replies()
        results["replies_drafted"] = replies
        self.stats["replies_drafted"] += replies

        # Step 5: Alerts & Notifications
        alerts = await self.job_dispatch_alerts()
        results["alerts_sent"] = alerts
        self.stats["alerts_sent"] += alerts

        log_event(
            f"Cycle finished: {ingested} posts, {matches} matches, {analyzed} analyzed, {replies} replies, {alerts} alerts.",
            "info",
            results,
        )
        return results

    async def job_poll_subreddits(self) -> int:
        """Poll monitored subreddits and ingest new posts."""
        subs_to_poll = set()
        with get_session() as session:
            rule_repo = RuleRepository(session)
            active_rules = rule_repo.get_all_active()
            for r in active_rules:
                for rs in (r.rule_subreddits or []):
                    if not rs.is_excluded and rs.subreddit_name and rs.subreddit_name.lower() != "all":
                        subs_to_poll.add(rs.subreddit_name.lower().replace("r/", ""))

        # Fallback default target communities
        if not subs_to_poll:
            subs_to_poll = {"saas", "startups", "webdev", "entrepreneur", "smallbusiness"}

        total_new_posts = 0

        for sub in list(subs_to_poll)[:6]:
            try:
                submissions = await self.submission_fetcher.fetch_subreddit_new(sub, limit=20)
                if submissions:
                    with get_session() as session:
                        post_repo = PostRepository(session)
                        for s in submissions:
                            _, is_new = post_repo.upsert_post(
                                reddit_id=s.reddit_id,
                                subreddit=s.subreddit,
                                title=s.title,
                                body=s.body,
                                author=s.author,
                                url=s.url,
                                permalink=s.permalink,
                                score=s.score,
                                num_comments=s.num_comments,
                                upvote_ratio=s.upvote_ratio,
                                post_flair=s.post_flair,
                                post_type=s.post_type,
                                thumbnail_url=s.thumbnail_url,
                                awards_count=s.awards_count,
                                posted_at=s.posted_at,
                            )
                            if is_new:
                                total_new_posts += 1
                        session.commit()
                await asyncio.sleep(1.0)
            except Exception as e:
                log_event(f"Error polling r/{sub}: {e}", "warning")

        return total_new_posts

    async def job_match_posts(self) -> int:
        """Match recent posts against active monitoring rules."""
        with get_session() as session:
            post_repo = PostRepository(session)
            rule_repo = RuleRepository(session)
            match_repo = MatchRepository(session)

            active_rules = rule_repo.get_all_active()
            if not active_rules:
                return 0

            # Get unmatched posts from the last 72 hours
            recent_posts = (
                session.query(RedditPost)
                .order_by(RedditPost.id.desc())
                .limit(100)
                .all()
            )

            new_matches = 0
            for post in recent_posts:
                for rule in active_rules:
                    # Check if match already exists
                    existing = (
                        session.query(Match)
                        .filter(Match.rule_id == rule.id, Match.post_id == post.id)
                        .first()
                    )
                    if existing:
                        continue

                    match_res = self.matching_engine.evaluate_post(post, rule)
                    if match_res.matched:
                        match_repo.create_match(
                            workspace_id=rule.workspace_id,
                            rule_id=rule.id,
                            post_id=post.id,
                            match_score=match_res.score,
                            match_reasons=match_res.reasons,
                        )
                        new_matches += 1

            session.commit()
            return new_matches

    async def job_analyze_matches(self) -> int:
        """Run deep AI intelligence & opportunity scoring on new matches."""
        with get_session() as session:
            match_repo = MatchRepository(session)
            analysis_repo = AnalysisRepository(session)
            comment_repo = CommentRepository(session)

            # Find matches lacking analysis
            unmatched = (
                session.query(Match)
                .outerjoin(Match.opportunity)
                .filter(Match.opportunity == None)
                .limit(15)
                .all()
            )

            analyzed_count = 0
            for match in unmatched:
                post = match.post
                if not post:
                    continue

                # Run intent classification & deep analysis
                intent_res = await self.intent_classifier.classify(post.body or "", post.title)
                deep_res = await self.post_analyzer.analyze(post, top_comments=[])

                # Persist post analysis
                analysis = analysis_repo.save_analysis(
                    post_id=post.id,
                    summary=deep_res.summary,
                    what_it_means=deep_res.what_it_means,
                    what_it_requires=deep_res.what_it_requires,
                    urgency=deep_res.urgency,
                    sentiment=deep_res.sentiment,
                    intent_tag=intent_res.tag,
                    intent_confidence=intent_res.confidence,
                    buy_signal_strength=deep_res.buy_signal_strength,
                    pain_strength=deep_res.pain_strength,
                    engagement_potential=deep_res.engagement_potential,
                    mentioned_products=deep_res.mentioned_products,
                    pain_keywords=deep_res.pain_keywords,
                    requirements=deep_res.requirements,
                    goals=deep_res.goals,
                    competitors=deep_res.competitors,
                    recommended_angle=deep_res.recommended_angle,
                    reddit_context=deep_res.reddit_context,
                    community_signals=deep_res.community_signals,
                    is_fallback=deep_res.is_fallback,
                )

                # Calculate deterministic 7-factor opportunity score
                opp_breakdown = OpportunityScorer.calculate(match, post, analysis)
                analysis_repo.save_opportunity_score(
                    match_id=match.id,
                    total_score=opp_breakdown.total_score,
                    relevance_score=opp_breakdown.relevance_score,
                    buying_signal_score=opp_breakdown.buying_signal_score,
                    pain_score=opp_breakdown.pain_score,
                    urgency_score=opp_breakdown.urgency_score,
                    engagement_score=opp_breakdown.engagement_score,
                    freshness_score=opp_breakdown.freshness_score,
                    community_fit_score=opp_breakdown.community_fit_score,
                    recommended_action=opp_breakdown.recommended_action,
                )
                analyzed_count += 1

            session.commit()
            return analyzed_count

    async def job_draft_replies(self) -> int:
        """Draft multi-strategy replies for high-opportunity matches."""
        with get_session() as session:
            match_repo = MatchRepository(session)
            reply_repo = ReplyRepository(session)

            high_opps = (
                session.query(Match)
                .join(Match.opportunity)
                .filter(Match.reply_drafts == None)
                .limit(10)
                .all()
            )

            drafted_count = 0
            for match in high_opps:
                post = match.post
                analysis = post.analysis if post else None
                if not post or not analysis:
                    continue

                angle = analysis.recommended_angle
                reply_res = await self.reply_generator.generate_reply(
                    title=post.title,
                    content=post.body or "",
                    subreddit=post.subreddit,
                    intent_tag=analysis.intent_tag or "question",
                    strategy="DIRECT_ANSWER",
                    recommended_angle=angle,
                )

                reply_repo.create_draft(
                    match_id=match.id,
                    post_id=post.id,
                    content=reply_res.content,
                    strategy=reply_res.strategy,
                    model_used=reply_res.model_used,
                    critic_scorecard=reply_res.critic.to_dict(),
                    promotion_risk=reply_res.critic.promotion_risk,
                    is_safe=reply_res.critic.is_safe,
                )
                drafted_count += 1

            session.commit()
            return drafted_count

    async def job_dispatch_alerts(self) -> int:
        """Dispatch instant alerts for newly discovered high-intent opportunities."""
        min_score = settings.alerts.min_opportunity_score or 70
        with get_session() as session:
            notif_repo = NotificationRepository(session)

            high_opps = (
                session.query(Match)
                .join(Match.opportunity)
                .filter(Match.notifications == None)
                .all()
            )

            sent_count = 0
            for match in high_opps:
                post = match.post
                opp = match.opportunity
                if not post or not opp:
                    continue

                if opp.total_score < min_score:
                    continue

                title = f"Opportunity ({opp.total_score}/100): {post.title[:70]}"
                msg = f"Subreddit: r/{post.subreddit}\nScore: {opp.total_score}\nVerdict: {opp.recommended_action}\nLink: {post.permalink or post.url}"

                # Send push alert
                if self.push_sender.is_configured():
                    success = await self.push_sender.send(
                        title=title,
                        message=msg,
                        url=post.permalink or post.url,
                        tags=["target", "reddit"],
                    )
                    notif_repo.create_record(
                        workspace_id=match.workspace_id,
                        match_id=match.id,
                        title=title,
                        message=msg,
                        channel="ntfy",
                        status="sent" if success else "failed",
                    )
                    if success:
                        sent_count += 1

            session.commit()
            return sent_count


# Global singleton job runner
job_runner = JobRunner()
