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

# Keep in-memory ring buffer of recent activity logs
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
        with get_session() as session:
            rule_repo = RuleRepository(session)
            active_rules = rule_repo.get_all_active()

            # Collect unique subreddits from rules + settings
            subs_to_poll = set(settings.reddit.subreddits)
            for r in active_rules:
                for rs in (r.rule_subreddits or []):
                    if not rs.is_excluded and rs.subreddit_name:
                        subs_to_poll.add(rs.subreddit_name.lower().replace("r/", ""))

        if not subs_to_poll:
            subs_to_poll = {"all"}

        total_new_posts = 0
        with get_session() as session:
            post_repo = PostRepository(session)

            for sub in subs_to_poll:
                try:
                    submissions = await self.submission_fetcher.fetch_subreddit_new(sub, limit=25)
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

            # Get recent unarchived posts from last 72 hours
            recent_posts, _ = post_repo.get_recent(hours=72, limit=150)
            new_matches = 0

            for post in recent_posts:
                for rule in active_rules:
                    res = self.matching_engine.evaluate_post(post, rule)
                    if res.is_match:
                        _, is_new = match_repo.create_match(
                            workspace_id=rule.workspace_id,
                            rule_id=rule.id,
                            post_id=post.id,
                            match_score=res.match_score,
                            match_reasons=res.match_reasons,
                        )
                        if is_new:
                            new_matches += 1

        return new_matches

    async def job_analyze_matches(self) -> int:
        """Run deep AI intelligence & calculate opportunity scores for matches."""
        with get_session() as session:
            match_repo = MatchRepository(session)
            analysis_repo = AnalysisRepository(session)
            comment_repo = CommentRepository(session)

            # Get matches without opportunity scores
            matches, _ = match_repo.get_opportunities(limit=30)
            analyzed_count = 0

            for match in matches:
                if not match.post:
                    continue

                post = match.post
                analysis = analysis_repo.get_by_post_id(post.id)

                if not analysis:
                    # Ingest top comments for richer context if needed
                    top_comments = []
                    if post.num_comments and post.num_comments > 0:
                        try:
                            norm_comments = await self.comment_fetcher.fetch_post_comments(
                                subreddit=post.subreddit,
                                post_reddit_id=post.reddit_id,
                                limit=5,
                            )
                            for nc in norm_comments:
                                c, _ = comment_repo.upsert_comment(
                                    reddit_id=nc.reddit_id,
                                    post_id=post.id,
                                    body=nc.body,
                                    author=nc.author,
                                    score=nc.score,
                                    permalink=nc.permalink,
                                    posted_at=nc.posted_at,
                                )
                                top_comments.append(c)
                        except Exception:
                            pass

                    # Step 1: Classify intent
                    intent_res = await self.intent_classifier.classify(post.body or "", post.title)

                    # Step 2: Deep post & community analysis
                    deep_res = await self.post_analyzer.analyze(post, top_comments=top_comments)

                    # Step 3: Save analysis
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
                    analyzed_count += 1

                # Calculate deterministic Opportunity Score
                if analysis:
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

        return analyzed_count

    async def job_draft_replies(self) -> int:
        """Draft multi-strategy replies for actionable high-opportunity matches."""
        with get_session() as session:
            match_repo = MatchRepository(session)
            reply_repo = ReplyRepository(session)

            matches, _ = match_repo.get_opportunities(min_opportunity=60, limit=20)
            drafted_count = 0

            for match in matches:
                if not match.post:
                    continue

                existing_replies = reply_repo.get_by_match_id(match.id)
                if not existing_replies:
                    post = match.post
                    analysis = post.analysis

                    intent_tag = analysis.intent_tag if analysis else "question"
                    angle = analysis.recommended_angle if analysis else None

                    # Default to direct answer or value first
                    strategy = "VALUE_FIRST" if intent_tag == "pain-point" else "DIRECT_ANSWER"

                    res = await self.reply_generator.generate_reply(
                        title=post.title,
                        content=post.body or "",
                        subreddit=post.subreddit,
                        intent_tag=intent_tag,
                        strategy=strategy,
                        recommended_angle=angle,
                    )

                    reply_repo.create_draft(
                        match_id=match.id,
                        post_id=post.id,
                        content=res.content,
                        strategy=res.strategy,
                        model_used=res.model_used,
                        critic_scorecard=res.critic.to_dict(),
                        promotion_risk=res.critic.promotion_risk,
                        is_safe=res.critic.is_safe,
                    )
                    drafted_count += 1

        return drafted_count

    async def job_dispatch_alerts(self) -> int:
        """Dispatch real-time notifications for high-opportunity leads."""
        with get_session() as session:
            match_repo = MatchRepository(session)
            notif_repo = NotificationRepository(session)

            # Find high-score matches that haven't been alerted
            matches, _ = match_repo.get_opportunities(
                min_opportunity=settings.alerts.min_opportunity_score,
                limit=10,
            )
            sent_count = 0

            for match in matches:
                if not match.post or match.notifications:
                    continue  # already notified

                post = match.post
                opp = match.opportunity
                score = opp.total_score if opp else int(match.match_score)

                title = f"🔥 Opportunity ({score}/100) in r/{post.subreddit}"
                msg = f"{post.title}\n\nURL: {post.permalink or post.url}"

                # Send via ntfy
                if settings.alerts.ntfy_topic:
                    try:
                        await self.push_sender.send(
                            title=title,
                            message=msg,
                            url=post.permalink or post.url,
                            tags=["fire", "reddit"],
                            priority="high" if score >= 80 else "default",
                        )
                        notif_repo.create_notification(
                            workspace_id=match.workspace_id,
                            match_id=match.id,
                            title=title,
                            message=msg,
                            channel="ntfy",
                            status="sent",
                        )
                        sent_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to send ntfy alert: {e}")

        return sent_count


# Global singleton runner
job_runner = JobRunner()
