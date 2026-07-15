import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.dashboard import DashboardOverview
from services.redis_service import RedisService, RedisStatus


class FakeRedisClient:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.set_calls: list[tuple[str, str, int | None]] = []
        self.deleted_keys: list[str] = []

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.values[key] = value
        self.set_calls.append((key, value, ex))
        return True

    def delete(self, *keys: str) -> int:
        self.deleted_keys.extend(keys)
        for key in keys:
            self.values.pop(key, None)
        return len(keys)


class TestDashboardCache(unittest.TestCase):
    def setUp(self) -> None:
        from services.dashboard_cache_service import DashboardCache

        self.client = FakeRedisClient()
        self.cache = DashboardCache(
            redis_service=RedisService(self.client, RedisStatus("connected", "available")),
            ttl_seconds=60,
        )

    def test_reuses_cached_dashboard_value_with_configured_ttl(self) -> None:
        calls = 0

        def load_overview() -> DashboardOverview:
            nonlocal calls
            calls += 1
            return DashboardOverview(
                ticket_total=2,
                pending_ticket_count=1,
                high_priority_pending_ticket_count=1,
                agent_run_total=3,
                average_run_duration_ms=120.0,
                agent_run_success_rate=1.0,
                feishu_notification_attempt_count=1,
                feishu_notification_success_rate=1.0,
            )

        first = self.cache.get_or_load_overview(load_overview)
        second = self.cache.get_or_load_overview(load_overview)

        self.assertEqual(first.ticket_total, 2)
        self.assertEqual(second.ticket_total, 2)
        self.assertEqual(calls, 1)
        self.assertEqual(self.client.set_calls[0][0], "dashboard:overview")
        self.assertEqual(self.client.set_calls[0][2], 60)

    def test_invalidation_removes_all_dashboard_cache_keys(self) -> None:
        self.cache.invalidate()

        self.assertEqual(
            self.client.deleted_keys,
            ["dashboard:overview", "dashboard:ticket-stats", "dashboard:agent-performance"],
        )
