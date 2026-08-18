"""
Competitor Repository for Competitor Intelligence & Automatic Rule Tracking.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.database.models import Competitor


class CompetitorRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_competitor(
        self,
        workspace_id: int,
        name: str,
        website: Optional[str] = None,
        tracked_keywords: Optional[List[str]] = None,
        auto_rule_id: Optional[int] = None,
    ) -> Competitor:
        # Generate default competitor keywords if none provided
        if not tracked_keywords:
            cname = name.strip()
            tracked_keywords = [
                f"{cname} alternative",
                f"{cname} replacement",
                f"switch from {cname}",
                f"leaving {cname}",
                f"{cname} pricing",
                f"{cname} expensive",
                f"{cname} limitations",
                f"{cname} vs",
            ]

        comp = Competitor(
            workspace_id=workspace_id,
            name=name.strip(),
            website=website,
            tracked_keywords=tracked_keywords,
            auto_rule_id=auto_rule_id,
            created_at=datetime.utcnow(),
        )
        self.session.add(comp)
        self.session.flush()
        return comp

    def get_all(self, workspace_id: Optional[int] = None) -> List[Competitor]:
        q = self.session.query(Competitor)
        if workspace_id:
            q = q.filter(Competitor.workspace_id == workspace_id)
        return q.order_by(desc(Competitor.created_at)).all()

    def get_by_id(self, competitor_id: int) -> Optional[Competitor]:
        return self.session.query(Competitor).filter(Competitor.id == competitor_id).first()

    def delete(self, competitor_id: int) -> bool:
        comp = self.get_by_id(competitor_id)
        if comp:
            self.session.delete(comp)
            self.session.flush()
            return True
        return False
