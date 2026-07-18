from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.business import Logistics, Ticket
from schemas.dashboard import RiskRanking, RiskRankingItem
from services.dashboard_service import PENDING_TICKET_STATUSES
from services.redis_service import RedisService


@dataclass(frozen=True)
class RiskRankingKeys:
    carrier_risks: str = "risk:carrier:abnormal_logistics"
    high_priority_tickets: str = "risk:tickets:high_priority_pending"
    frequent_issue_risks: str = "risk:issues:frequent_after_sales"


class RiskRankingService:
    """Maintains Redis sorted-set risk rankings with a SQLite fallback."""

    def __init__(self, *, redis_service: RedisService, keys: RiskRankingKeys | None = None) -> None:
        self.redis_service = redis_service
        self.keys = keys or RiskRankingKeys()

    @classmethod
    def from_environment(cls) -> "RiskRankingService":
        return cls(redis_service=RedisService.from_environment())

    def get_rankings(self, db: Session) -> RiskRanking:
        client = self.redis_service.client
        if client is None:
            return build_sqlite_risk_ranking(db, source="sqlite_fallback")

        try:
            ranking = build_sqlite_risk_ranking(db, source="redis")
            self._replace_zset(self.keys.carrier_risks, ranking.carrier_risks)
            self._replace_zset(self.keys.high_priority_tickets, ranking.high_priority_tickets)
            self._replace_zset(self.keys.frequent_issue_risks, ranking.frequent_issue_risks)
            return RiskRanking(
                source="redis",
                carrier_risks=self._read_zset(self.keys.carrier_risks),
                high_priority_tickets=self._read_zset(self.keys.high_priority_tickets, count_from_score=False),
                frequent_issue_risks=self._read_zset(self.keys.frequent_issue_risks),
            )
        except Exception:
            return build_sqlite_risk_ranking(db, source="sqlite_fallback")

    def refresh(self, db: Session) -> None:
        client = self.redis_service.client
        if client is None:
            return
        try:
            ranking = build_sqlite_risk_ranking(db, source="redis")
            self._replace_zset(self.keys.carrier_risks, ranking.carrier_risks)
            self._replace_zset(self.keys.high_priority_tickets, ranking.high_priority_tickets)
            self._replace_zset(self.keys.frequent_issue_risks, ranking.frequent_issue_risks)
        except Exception:
            return

    def _replace_zset(self, key: str, items: list[RiskRankingItem]) -> None:
        client = self.redis_service.client
        if client is None:
            return
        client.delete(key)
        if items:
            client.zadd(key, {item.key: item.score for item in items})

    def _read_zset(self, key: str, limit: int = 10, *, count_from_score: bool = True) -> list[RiskRankingItem]:
        client = self.redis_service.client
        if client is None:
            return []
        rows = client.zrevrange(key, 0, limit - 1, withscores=True)
        return [
            RiskRankingItem(key=str(member), score=float(score), count=int(score) if count_from_score else 1)
            for member, score in rows
        ]


def build_sqlite_risk_ranking(db: Session, *, source: str) -> RiskRanking:
    logistics_records = list(db.scalars(select(Logistics)))
    tickets = list(db.scalars(select(Ticket)))

    abnormal_carriers = Counter(
        logistics.carrier for logistics in logistics_records if logistics.is_abnormal
    )
    issue_counts = Counter(ticket.ticket_type for ticket in tickets)
    high_priority_pending = [
        ticket
        for ticket in tickets
        if ticket.priority == "high" and ticket.status in PENDING_TICKET_STATUSES
    ]

    return RiskRanking(
        source=source,
        carrier_risks=counter_to_ranking_items(abnormal_carriers),
        high_priority_tickets=[
            RiskRankingItem(key=ticket.ticket_id, score=ticket.updated_at.timestamp(), count=1)
            for ticket in sorted(high_priority_pending, key=lambda item: item.updated_at, reverse=True)
        ],
        frequent_issue_risks=counter_to_ranking_items(issue_counts),
    )


def counter_to_ranking_items(counter: Counter[str]) -> list[RiskRankingItem]:
    return [
        RiskRankingItem(key=key, score=float(count), count=count)
        for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def refresh_risk_rankings(db: Session) -> None:
    RiskRankingService.from_environment().refresh(db)
