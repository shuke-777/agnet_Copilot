import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from api.main import app


class TestCopilotAnalyzeApi(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_analyze_creates_ticket_for_abnormal_logistics(self) -> None:
        response = self.client.post(
            "/api/copilot/analyze",
            json={
                "session_id": "SESSION-COPILOT-001",
                "user_id": "USER-001",
                "user_message": "我的订单 ORD-1001 怎么还没收到？帮我催一下物流。",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["intent"], "logistics_delay")
        self.assertEqual(body["order_id"], "ORD-1001")
        self.assertTrue(body["is_abnormal"])
        self.assertTrue(body["ticket_created"])
        self.assertIsNotNone(body["ticket_id"])
        self.assertIn("物流超过 72 小时未更新", body["reply_draft"])

        ticket_response = self.client.get(f"/api/tickets/{body['ticket_id']}")
        self.assertEqual(ticket_response.status_code, 200)
        ticket = ticket_response.json()
        self.assertEqual(ticket["ticket_type"], "logistics_delay")
        self.assertEqual(ticket["status"], "todo")
        self.assertEqual(ticket["created_by"], "agent")

        steps_response = self.client.get(f"/api/runs/{body['run_id']}/steps")
        self.assertEqual(steps_response.status_code, 200)
        step_names = [step["step_name"] for step in steps_response.json()]
        self.assertEqual(
            step_names,
            [
                "intent_recognition",
                "order_extract",
                "order_query",
                "logistics_query",
                "abnormal_check",
                "reply_generate",
                "ticket_create",
            ],
        )

    def test_analyze_does_not_create_ticket_for_normal_logistics(self) -> None:
        response = self.client.post(
            "/api/copilot/analyze",
            json={
                "session_id": "SESSION-COPILOT-002",
                "user_id": "USER-002",
                "user_message": "帮我看一下订单 ORD-1002 的物流。",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["order_id"], "ORD-1002")
        self.assertFalse(body["is_abnormal"])
        self.assertFalse(body["ticket_created"])
        self.assertIsNone(body["ticket_id"])
        self.assertIn("物流状态正常", body["reply_draft"])

        steps_response = self.client.get(f"/api/runs/{body['run_id']}/steps")
        self.assertEqual(steps_response.status_code, 200)
        step_names = [step["step_name"] for step in steps_response.json()]
        self.assertNotIn("ticket_create", step_names)

    def test_analyze_returns_400_when_order_id_is_missing(self) -> None:
        response = self.client.post(
            "/api/copilot/analyze",
            json={
                "session_id": "SESSION-COPILOT-003",
                "user_id": "USER-003",
                "user_message": "我的订单怎么还没收到？",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Order id not found in user message")
