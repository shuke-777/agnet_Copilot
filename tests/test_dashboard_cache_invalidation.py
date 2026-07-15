import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from api.main import app


class TestDashboardCacheInvalidation(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch("api.business.invalidate_dashboard_cache")
    def test_creating_ticket_invalidates_dashboard_cache(self, invalidate_cache) -> None:
        response = self.client.post(
            "/api/tickets",
            json={
                "ticket_type": "logistics_delay",
                "priority": "high",
                "user_id": "USER-001",
                "order_id": "ORD-1001",
                "summary": "物流异常，需要催单",
                "suggested_action": "联系承运商",
                "created_by": "agent",
            },
        )

        self.assertEqual(response.status_code, 201)
        invalidate_cache.assert_called_once_with()

    @patch("services.copilot_service.invalidate_dashboard_cache")
    def test_completed_copilot_run_invalidates_dashboard_cache(self, invalidate_cache) -> None:
        response = self.client.post(
            "/api/copilot/analyze",
            json={
                "session_id": "SESSION-DASHBOARD-CACHE-001",
                "user_id": "USER-002",
                "user_message": "帮我看一下订单 ORD-1002 的物流。",
            },
        )

        self.assertEqual(response.status_code, 200)
        invalidate_cache.assert_called_once_with()

    @patch("api.feishu.invalidate_dashboard_cache")
    def test_processed_feishu_callback_invalidates_dashboard_cache(self, invalidate_cache) -> None:
        ticket_response = self.client.post(
            "/api/tickets",
            json={
                "ticket_type": "logistics_delay",
                "priority": "high",
                "user_id": "USER-001",
                "order_id": "ORD-1001",
                "summary": "物流异常，需要催单",
                "suggested_action": "联系承运商",
                "created_by": "agent",
            },
        )
        ticket_id = ticket_response.json()["ticket_id"]

        response = self.client.post(
            "/api/feishu/callback",
            json={
                "event_id": "FEISHU-CACHE-001",
                "ticket_id": ticket_id,
                "action": "claim",
                "operator": "客服A",
            },
        )

        self.assertEqual(response.status_code, 200)
        invalidate_cache.assert_called_once_with()
