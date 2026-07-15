import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.redis_service import RedisService


class TestRedisService(unittest.TestCase):
    def test_missing_url_disables_redis_without_creating_a_client(self) -> None:
        with patch.dict(os.environ, {"REDIS_URL": ""}, clear=False), patch(
            "services.redis_service.load_project_environment",
            return_value=False,
        ):
            service = RedisService.from_environment()

        self.assertIsNone(service.client)
        self.assertEqual(service.status.as_dict(), {"status": "disabled", "detail": "REDIS_URL is not configured"})

    def test_connection_failure_returns_unavailable_without_raising(self) -> None:
        def failing_factory(*args: object, **kwargs: object) -> object:
            raise OSError("connection refused")

        with patch.dict(os.environ, {"REDIS_URL": "redis://127.0.0.1:6379/0"}, clear=False), patch(
            "services.redis_service.load_project_environment",
            return_value=False,
        ):
            service = RedisService.from_environment(client_factory=failing_factory)

        self.assertIsNone(service.client)
        self.assertEqual(service.status.status, "unavailable")
        self.assertIn("connection refused", service.status.detail)

    def test_successful_connection_exposes_redis_client(self) -> None:
        class FakeRedisClient:
            def ping(self) -> bool:
                return True

        client = FakeRedisClient()

        def client_factory(*args: object, **kwargs: object) -> FakeRedisClient:
            return client

        with patch.dict(os.environ, {"REDIS_URL": "redis://127.0.0.1:6379/0"}, clear=False), patch(
            "services.redis_service.load_project_environment",
            return_value=False,
        ):
            service = RedisService.from_environment(client_factory=client_factory)

        self.assertIs(service.client, client)
        self.assertEqual(service.status.as_dict(), {"status": "connected", "detail": "Redis connection is available"})
