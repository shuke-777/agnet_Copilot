import unittest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from api.main import app
from models.agent_trace import AgentRun
from models.business import Order, Ticket
from models.database import SessionLocal
from services.bootstrap import seed_demo_data
from scripts.reset_demo_database import reset_demo_database


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

    def test_extended_demo_orders_cover_after_sales_scenarios(self) -> None:
        expected_orders = {
            "ORD-1003": ("宠物自动喂食器", "stalled", True),
            "ORD-1004": ("人体工学升降桌", "not_shipped", False),
            "ORD-1005": ("夏季防晒衣", "delivered", False),
            "ORD-1006": ("旗舰款扫地机器人", "in_transit", False),
            "ORD-1007": ("手机钢化膜", "in_transit", False),
            "ORD-1008": ("真皮通勤双肩包", "delivered", False),
            "ORD-1009": ("智能运动手表", "delivered", False),
            "ORD-1010": ("母婴恒温水壶", "in_transit", False),
            "ORD-1011": ("儿童学习平板", "not_shipped", False),
            "ORD-1012": ("便携咖啡机", "in_transit", False),
        }

        for order_id, (product_name, logistics_status, is_abnormal) in expected_orders.items():
            order_response = self.client.get(f"/api/orders/{order_id}")
            self.assertEqual(order_response.status_code, 200)
            self.assertEqual(order_response.json()["product_name"], product_name)

            logistics_response = self.client.get(f"/api/logistics/{order_id}")
            self.assertEqual(logistics_response.status_code, 200)
            self.assertEqual(logistics_response.json()["status"], logistics_status)
            self.assertEqual(logistics_response.json()["is_abnormal"], is_abnormal)

    def test_seed_demo_data_is_idempotent_for_existing_databases(self) -> None:
        with SessionLocal() as db:
            seed_demo_data(db)
            seed_demo_data(db)
            order_count = db.query(Order).count()

        self.assertEqual(order_count, 12)

    def test_reset_demo_database_clears_history_and_reseeds_demo_orders(self) -> None:
        with SessionLocal() as db:
            db.add(
                AgentRun(
                    run_id="RUN-RESET-001",
                    session_id="SESSION-RESET-001",
                    user_id="USER-001",
                    user_message="reset smoke",
                    status="success",
                )
            )
            db.add(
                Ticket(
                    ticket_id="TCK-RESET-001",
                    ticket_type="logistics_delay",
                    priority="high",
                    status="todo",
                    user_id="USER-001",
                    order_id="ORD-1001",
                    summary="reset smoke",
                    suggested_action="reset smoke",
                    created_by="agent",
                )
            )
            db.commit()

        reset_demo_database()

        with SessionLocal() as db:
            self.assertEqual(db.query(Order).count(), 12)
            self.assertEqual(db.query(AgentRun).count(), 0)
            self.assertEqual(db.query(Ticket).count(), 0)

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

    def test_ticket_action_updates_status_and_records_manual_event(self) -> None:
        create_response = self.client.post(
            "/api/tickets",
            json={
                "ticket_type": "logistics_delay",
                "priority": "high",
                "user_id": "USER-001",
                "order_id": "ORD-1001",
                "summary": "客户反馈订单一直没有收到，需要催物流。",
                "suggested_action": "联系承运商核实卡点。",
                "created_by": "agent",
            },
        )
        ticket_id = create_response.json()["ticket_id"]

        response = self.client.post(
            f"/api/tickets/{ticket_id}/actions",
            json={"action": "claim", "operator": "客服A"},
        )

        self.assertEqual(response.status_code, 200)
        ticket = response.json()
        self.assertEqual(ticket["status"], "processing")
        self.assertEqual(ticket["assigned_to"], "客服A")
        self.assertEqual(ticket["events"][-1]["event_type"], "manual_status_changed")
        self.assertEqual(ticket["events"][-1]["from_status"], "todo")
        self.assertEqual(ticket["events"][-1]["to_status"], "processing")

    def test_tickets_can_be_filtered_by_ticket_run_or_order_id(self) -> None:
        created = self.client.post(
            "/api/tickets",
            json={
                "ticket_type": "logistics_delay",
                "priority": "high",
                "user_id": "USER-001",
                "order_id": "ORD-1001",
                "summary": "用于检索测试的工单。",
                "suggested_action": "人工跟进。",
                "created_by": "manual",
            },
        ).json()

        self.assertEqual(self.client.get(f"/api/tickets?q={created['ticket_id']}").json()[0]["ticket_id"], created["ticket_id"])
        self.assertEqual(self.client.get("/api/tickets?q=ORD-1001").json()[0]["order_id"], "ORD-1001")
