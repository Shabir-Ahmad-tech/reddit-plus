"""
Monitoring Rule Repository.
"""

from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from src.database.models import MonitoringRule, RuleKeyword, RuleSubreddit, RuleExclusion


class RuleRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_rule(
        self,
        workspace_id: int,
        name: str,
        description: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        subreddits: Optional[List[str]] = None,
        exclusions: Optional[List[str]] = None,
        min_score: int = 1,
        min_comments: int = 0,
        min_opportunity_score: int = 60,
        max_age_hours: int = 72,
        target_intents: Optional[List[str]] = None,
        notify_ntfy: bool = True,
        notify_email: bool = False,
        notify_webhook: bool = False,
    ) -> MonitoringRule:
        rule = MonitoringRule(
            workspace_id=workspace_id,
            name=name,
            description=description,
            min_score=min_score,
            min_comments=min_comments,
            min_opportunity_score=min_opportunity_score,
            max_age_hours=max_age_hours,
            target_intents=target_intents or ["buy-intent", "seeking-alternatives", "pain-point", "question"],
            notify_ntfy=notify_ntfy,
            notify_email=notify_email,
            notify_webhook=notify_webhook,
        )
        self.session.add(rule)
        self.session.flush()

        if keywords:
            for kw in keywords:
                if kw and kw.strip():
                    self.session.add(RuleKeyword(rule_id=rule.id, keyword=kw.strip()))

        if subreddits:
            for sub in subreddits:
                clean_sub = sub.replace("r/", "").strip()
                if clean_sub:
                    self.session.add(RuleSubreddit(rule_id=rule.id, subreddit_name=clean_sub))

        if exclusions:
            for exc in exclusions:
                if exc and exc.strip():
                    self.session.add(RuleExclusion(rule_id=rule.id, pattern=exc.strip()))

        self.session.flush()
        return rule

    def get_by_id(self, rule_id: int) -> Optional[MonitoringRule]:
        return (
            self.session.query(MonitoringRule)
            .options(
                joinedload(MonitoringRule.keywords),
                joinedload(MonitoringRule.rule_subreddits),
                joinedload(MonitoringRule.exclusions),
            )
            .filter(MonitoringRule.id == rule_id)
            .first()
        )

    def get_all_active(self, workspace_id: Optional[int] = None) -> List[MonitoringRule]:
        q = (
            self.session.query(MonitoringRule)
            .options(
                joinedload(MonitoringRule.keywords),
                joinedload(MonitoringRule.rule_subreddits),
                joinedload(MonitoringRule.exclusions),
            )
            .filter(MonitoringRule.is_active == True)
        )
        if workspace_id:
            q = q.filter(MonitoringRule.workspace_id == workspace_id)
        return q.all()

    def get_all(self, workspace_id: Optional[int] = None) -> List[MonitoringRule]:
        q = self.session.query(MonitoringRule).options(
            joinedload(MonitoringRule.keywords),
            joinedload(MonitoringRule.rule_subreddits),
            joinedload(MonitoringRule.exclusions),
        )
        if workspace_id:
            q = q.filter(MonitoringRule.workspace_id == workspace_id)
        return q.order_by(desc(MonitoringRule.created_at)).all()

    def toggle_active(self, rule_id: int, active: bool) -> Optional[MonitoringRule]:
        rule = self.get_by_id(rule_id)
        if rule:
            rule.is_active = active
            self.session.flush()
        return rule

    def delete(self, rule_id: int) -> bool:
        rule = self.get_by_id(rule_id)
        if rule:
            self.session.delete(rule)
            self.session.flush()
            return True
        return False
