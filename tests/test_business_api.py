import unittest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from api.main import app


class TestBusinessApi(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_get_order_returns_seed_order(self) -> None:
        response = self.client.get("/api/orders/ORD-1001")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["order_id"], "ORD-1001")
        self.assertEqual(body["user_id"], "USER-001")
        self.assertEqual(body["product_name"], "无线蓝牙耳机")
        self.assertEqual(body["status"], "shipped")

    def test_get_logistics_returns_abnormal_seed_logistics(self) -> None:
        response = self.client.get("/api/logistics/ORD-1001")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["order_id"], "ORD-1001")
        self.assertEqual(body["carrier"], "顺丰速运")
        self.assertTrue(body["is_abnormal"])
        self.assertIn("物流超过 72 小时未更新", body["last_event"])

    def test_get_unknown_order_returns_404(self) -> None:
        response = self.client.get("/api/orders/ORD-NOT-FOUND")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Order not found")

    def test_ticket_can_be_created_updated_and_appended_with_events(self) -> None:
        create_response = self.client.post(
            "/api/tickets",
            json={
                "ticket_type": "logistics_delay",
                "priority": "high",
                "user_id": "USER-001",
                "order_id": "ORD-1001",
                "summary": "客户反馈订单一直没有收到，需要催物流。",
                "suggested_action": "联系承运商核实卡点，并同步客户预计处理时效。",
                "created_by": "agent",
            },
        )

        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["status"], "todo")
        self.assertEqual(created["order_id"], "ORD-1001")
        ticket_id = created["ticket_id"]

        get_response = self.client.get(f"/api/tickets/{ticket_id}")
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["ticket_id"], ticket_id)

        update_response = self.client.patch(
            f"/api/tickets/{ticket_id}",
            json={
                "status": "processing",
                "assigned_to": "客服A",
            },
        )
        self.assertEqual(update_response.status_code, 200)
        updated = update_response.json()
        self.assertEqual(updated["status"], "processing")
        self.assertEqual(updated["assigned_to"], "客服A")

        event_response = self.client.post(
            f"/api/tickets/{ticket_id}/events",
            json={
                "event_type": "status_changed",
                "operator": "客服A",
                "content": "已联系承运商，等待反馈。",
                "from_status": "todo",
                "to_status": "processing",
            },
        )
        self.assertEqual(event_response.status_code, 201)
        event = event_response.json()
        self.assertEqual(event["ticket_id"], ticket_id)
        self.assertEqual(event["to_status"], "processing")

        list_response = self.client.get("/api/tickets")
        self.assertEqual(list_response.status_code, 200)
        ticket_ids = {item["ticket_id"] for item in list_response.json()}
        self.assertIn(ticket_id, ticket_ids)
