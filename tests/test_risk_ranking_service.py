import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.business import make_id
from models.business import Ticket
from models.database import SessionLocal
from services.redis_service import RedisService, RedisStatus
from services.risk_ranking_service import RiskRankingService


class FakeSortedSetRedisClient:
    def __init__(self) -> None:
        self.sorted_sets: dict[str, dict[str, float]] = {}
        self.deleted_keys: list[str] = []

    def delete(self, *keys: str) -> int:
        self.deleted_keys.extend(keys)
        for key in keys:
            self.sorted_sets.pop(key, None)
        return len(keys)

    def zadd(self, key: str, mapping: dict[str, float]) -> int:
        self.sorted_sets.setdefault(key, {}).update(mapping)
        return len(mapping)

    def zrevrange(self, key: str, start: int, end: int, withscores: bool = False):
        rows = sorted(
            self.sorted_sets.get(key, {}).items(),
            key=lambda item: (-item[1], item[0]),
        )
        selected = rows[start : end + 1]
        if withscores:
            return selected
        return [key for key, _ in selected]


class TestRiskRankingService(unittest.TestCase):
    def test_refreshes_and_reads_redis_sorted_set_rankings(self) -> None:
        with SessionLocal() as db:
            db.add_all(
                [
                    Ticket(
                        ticket_id=make_id("TCK"),
                        ticket_type="logistics_delay",
                        priority="high",
                        status="todo",
                        user_id="USER-001",
                        order_id="ORD-1001",
                        summary="待处理异常物流工单",
                        suggested_action="联系承运商",
                        created_by="agent",
                    ),
                    Ticket(
                        ticket_id=make_id("TCK"),
                        ticket_type="refund",
                        priority="normal",
                        status="resolved",
                        user_id="USER-002",
                        order_id="ORD-1002",
                        summary="已解决退款咨询",
                        suggested_action="无需进一步操作",
                        created_by="agent",
                    ),
                ]
            )
            db.commit()

            redis_client = FakeSortedSetRedisClient()
            service = RiskRankingService(
                redis_service=RedisService(redis_client, RedisStatus("connected", "available")),
            )

            ranking = service.get_rankings(db)

        self.assertEqual(ranking.source, "redis")
        carrier_risks = {item.key: item for item in ranking.carrier_risks}
        self.assertEqual(carrier_risks["顺丰速运"].score, 1.0)
        self.assertEqual(ranking.high_priority_tickets[0].count, 1)
        self.assertGreater(ranking.high_priority_tickets[0].score, 1.0)
        self.assertEqual(ranking.frequent_issue_risks[0].key, "logistics_delay")
        self.assertIn("risk:carrier:abnormal_logistics", redis_client.deleted_keys)
