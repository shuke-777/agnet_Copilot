import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.rate_limit_service import CopilotRateLimiter
from services.redis_service import RedisService, RedisStatus


class TestCopilotRateLimiter(unittest.TestCase):
    def test_unavailable_redis_fails_open_for_local_development(self) -> None:
        limiter = CopilotRateLimiter(
            redis_service=RedisService(None, RedisStatus("unavailable", "connection refused")),
            capacity=10,
            window_seconds=60,
        )

        result = limiter.consume("USER-001")

        self.assertTrue(result.allowed)
        self.assertEqual(result.retry_after_seconds, 0)
        self.assertEqual(result.fallback_reason, "Redis rate limiting is unavailable")

    def test_rejected_bucket_returns_retry_after_seconds(self) -> None:
        class RejectingRedisClient:
            def eval(self, *args: object) -> list[int]:
                return [0, 0, 12]

        limiter = CopilotRateLimiter(
            redis_service=RedisService(RejectingRedisClient(), RedisStatus("connected", "available")),
            capacity=10,
            window_seconds=60,
        )

        result = limiter.consume("USER-001")

        self.assertFalse(result.allowed)
        self.assertEqual(result.retry_after_seconds, 12)
