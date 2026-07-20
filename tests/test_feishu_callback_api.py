import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from api.main import app
from models.database import SessionLocal


class TestFeishuCallbackApi(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        response = self.client.post(
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
        self.assertEqual(response.status_code, 201)
        self.ticket_id = response.json()["ticket_id"]

    def callback(self, action: str, event_id: str, operator: str = "客服A"):
        return self.client.post(
            "/api/feishu/callback",
            json={
                "event_id": event_id,
                "ticket_id": self.ticket_id,
                "action": action,
                "operator": operator,
            },
        )

    def create_approval_ticket(self) -> str:
        response = self.client.post(
            "/api/tickets",
            json={
                "ticket_type": "refund_approval",
                "priority": "high",
                "user_id": "USER-001",
                "order_id": "ORD-1001",
                "summary": "用户申请订单 ORD-1001 退款，需要人工审核。",
                "suggested_action": "请审核是否允许为订单 ORD-1001 发起退款处理。",
                "created_by": "agent",
                "approval_required": True,
                "approval_status": "pending",
                "approval_reason": "退款涉及资金动作，需要人工审核",
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["ticket_id"]

    def test_callback_returns_challenge_for_feishu_url_verification(self) -> None:
        response = self.client.post(
            "/api/feishu/callback",
            json={
                "challenge": "FEISHU-URL-VERIFY-001",
                "token": "demo-token",
                "type": "url_verification",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"challenge": "FEISHU-URL-VERIFY-001"})

    def test_callback_updates_ticket_and_records_both_events(self) -> None:
        response = self.callback("claim", "FEISHU-EVENT-001")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["ticket"]["status"], "processing")
        self.assertEqual(body["ticket"]["assigned_to"], "客服A")
        self.assertEqual(body["feishu_event"]["event_id"], "FEISHU-EVENT-001")
        self.assertEqual(body["feishu_event"]["status"], "processed")

        ticket = self.client.get(f"/api/tickets/{self.ticket_id}").json()
        self.assertEqual(len(ticket["events"]), 1)
        self.assertEqual(ticket["events"][0]["event_type"], "feishu_status_changed")
        self.assertEqual(ticket["events"][0]["to_status"], "processing")

        with SessionLocal() as db:
            from models.feishu_event import FeishuEvent

            event = db.get(FeishuEvent, "FEISHU-EVENT-001")
            self.assertIsNotNone(event)
            self.assertEqual(event.ticket_id, self.ticket_id)
            self.assertEqual(event.action, "claim")
            self.assertEqual(event.status, "processed")

    def test_callback_supports_resolve_and_reopen(self) -> None:
        self.assertEqual(self.callback("claim", "FEISHU-EVENT-002").status_code, 200)
        resolve_response = self.callback("resolve", "FEISHU-EVENT-003")
        reopen_response = self.callback("reopen", "FEISHU-EVENT-004")

        self.assertEqual(resolve_response.status_code, 200)
        self.assertEqual(resolve_response.json()["ticket"]["status"], "resolved")
        self.assertEqual(reopen_response.status_code, 200)
        self.assertEqual(reopen_response.json()["ticket"]["status"], "processing")

    def test_callback_supports_approval_actions(self) -> None:
        self.ticket_id = self.create_approval_ticket()
        response = self.callback("approve", "FEISHU-APPROVAL-001", operator="主管A")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["ticket"]["approval_status"], "approved")
        self.assertEqual(body["ticket"]["approval_decided_by"], "主管A")
        self.assertEqual(body["ticket"]["status"], "processing")
        self.assertEqual(body["ticket_event"]["event_type"], "feishu_approval_changed")
        self.assertEqual(body["ticket_event"]["from_status"], "pending")
        self.assertEqual(body["ticket_event"]["to_status"], "approved")
        self.assertEqual(body["feishu_event"]["action"], "approve")

    def test_callback_supports_real_feishu_card_action_payload(self) -> None:
        self.ticket_id = self.create_approval_ticket()
        response = self.client.post(
            "/api/feishu/callback",
            json={
                "schema": "2.0",
                "header": {
                    "event_id": "FEISHU-REAL-CARD-001",
                    "event_type": "card.action.trigger",
                    "create_time": "1720000000000",
                    "token": "demo-token",
                },
                "event": {
                    "operator": {
                        "open_id": "ou_demo_operator",
                        "user_id": "user_demo_operator",
                    },
                    "action": {
                        "tag": "button",
                        "value": {
                            "ticket_id": self.ticket_id,
                            "action": "approve",
                        },
                    },
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body.keys()), {"toast", "card"})
        self.assertEqual(body["card"]["type"], "raw")
        self.assertEqual(body["card"]["data"]["schema"], "2.0")
        self.assertEqual(body["card"]["data"]["header"]["title"]["content"], "售后处理已通过")
        self.assertIn("elements", body["card"]["data"]["body"])

        ticket = self.client.get(f"/api/tickets/{self.ticket_id}").json()
        self.assertEqual(ticket["approval_status"], "approved")
        self.assertEqual(ticket["status"], "processing")
        with SessionLocal() as db:
            from models.feishu_event import FeishuEvent

            event = db.get(FeishuEvent, "FEISHU-REAL-CARD-001")
            self.assertIsNotNone(event)
            self.assertEqual(event.action, "approve")
            self.assertEqual(event.operator, "ou_demo_operator")
            self.assertIn("card.action.trigger", event.payload)

    def test_real_feishu_card_action_returns_updated_card_without_action_buttons(self) -> None:
        self.ticket_id = self.create_approval_ticket()
        response = self.client.post(
            "/api/feishu/callback",
            json={
                "schema": "2.0",
                "header": {
                    "event_id": "FEISHU-REAL-CARD-UPDATED-001",
                    "event_type": "card.action.trigger",
                    "create_time": "1720000000000",
                    "token": "demo-token",
                },
                "event": {
                    "operator": {"open_id": "ou_demo_operator"},
                    "action": {
                        "tag": "button",
                        "value": {
                            "ticket_id": self.ticket_id,
                            "action": "approve",
                        },
                    },
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["toast"]["type"], "success")
        self.assertEqual(set(body.keys()), {"toast", "card"})
        self.assertIn("审核通过", body["toast"]["content"])
        self.assertEqual(body["card"]["type"], "raw")
        self.assertEqual(body["card"]["data"]["schema"], "2.0")
        self.assertEqual(body["card"]["data"]["header"]["title"]["content"], "售后处理已通过")
        self.assertIn("elements", body["card"]["data"]["body"])
        card_text = str(body["card"])
        self.assertIn(self.ticket_id, card_text)
        self.assertIn("ou_demo_operator", card_text)
        self.assertNotIn('"action": "approve"', card_text)
        self.assertNotIn('"action": "reject"', card_text)
        self.assertNotIn('"action": "manual_confirm"', card_text)

        ticket = self.client.get(f"/api/tickets/{self.ticket_id}").json()
        self.assertEqual(ticket["approval_status"], "approved")
        self.assertEqual(ticket["status"], "processing")

    def test_real_feishu_card_action_is_idempotent_when_retry_uses_new_event_id(self) -> None:
        self.ticket_id = self.create_approval_ticket()
        first_payload = {
            "schema": "2.0",
            "header": {
                "event_id": "FEISHU-REAL-CARD-RETRY-001",
                "event_type": "card.action.trigger",
                "create_time": "1720000000000",
                "token": "demo-token",
            },
            "event": {
                "operator": {"open_id": "ou_demo_operator"},
                "action": {
                    "tag": "button",
                    "value": {
                        "ticket_id": self.ticket_id,
                        "action": "approve",
                    },
                },
            },
        }
        retry_payload = {
            **first_payload,
            "header": {
                **first_payload["header"],
                "event_id": "FEISHU-REAL-CARD-RETRY-002",
            },
        }

        first_response = self.client.post("/api/feishu/callback", json=first_payload)
        retry_response = self.client.post("/api/feishu/callback", json=retry_payload)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(retry_response.status_code, 200)
        body = retry_response.json()
        self.assertEqual(set(body.keys()), {"toast", "card"})
        self.assertEqual(body["card"]["type"], "raw")
        self.assertEqual(body["card"]["data"]["schema"], "2.0")
        self.assertEqual(body["card"]["data"]["header"]["title"]["content"], "售后处理已通过")
        self.assertNotIn('"action": "approve"', str(body["card"]))

        ticket = self.client.get(f"/api/tickets/{self.ticket_id}").json()
        self.assertEqual(ticket["approval_status"], "approved")

    def test_callback_supports_stringified_feishu_action_value(self) -> None:
        self.ticket_id = self.create_approval_ticket()
        response = self.client.post(
            "/api/feishu/callback",
            json={
                "uuid": "FEISHU-REAL-CARD-002",
                "type": "event_callback",
                "event": {
                    "type": "card.action.trigger",
                    "operator": {"user_id": "user_demo_operator"},
                    "action": {
                        "value": f'{{"ticket_id":"{self.ticket_id}","action":"reject"}}',
                    },
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body.keys()), {"toast", "card"})
        self.assertEqual(body["card"]["type"], "raw")
        self.assertEqual(body["card"]["data"]["schema"], "2.0")
        self.assertEqual(body["card"]["data"]["header"]["title"]["content"], "售后处理已拒绝")
        self.assertIn("elements", body["card"]["data"]["body"])

        ticket = self.client.get(f"/api/tickets/{self.ticket_id}").json()
        self.assertEqual(ticket["approval_status"], "rejected")
        self.assertEqual(ticket["status"], "resolved")
        with SessionLocal() as db:
            from models.feishu_event import FeishuEvent

            event = db.get(FeishuEvent, "FEISHU-REAL-CARD-002")
            self.assertIsNotNone(event)
            self.assertEqual(event.operator, "user_demo_operator")

    def test_callback_supports_reject_and_manual_confirm_approval_actions(self) -> None:
        first_ticket_id = self.create_approval_ticket()
        self.ticket_id = first_ticket_id
        reject_response = self.callback("reject", "FEISHU-APPROVAL-002", operator="主管A")
        self.assertEqual(reject_response.status_code, 200)
        self.assertEqual(reject_response.json()["ticket"]["approval_status"], "rejected")
        self.assertEqual(reject_response.json()["ticket"]["status"], "resolved")

        second_ticket_id = self.create_approval_ticket()
        self.ticket_id = second_ticket_id
        manual_response = self.callback("manual_confirm", "FEISHU-APPROVAL-003", operator="主管B")
        self.assertEqual(manual_response.status_code, 200)
        self.assertEqual(manual_response.json()["ticket"]["approval_status"], "pending")
        self.assertEqual(manual_response.json()["ticket"]["status"], "processing")

    def test_callback_is_idempotent_for_the_same_feishu_event_id(self) -> None:
        first_response = self.callback("claim", "FEISHU-EVENT-IDEMPOTENT-001")
        second_response = self.callback("claim", "FEISHU-EVENT-IDEMPOTENT-001")

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.json()["ticket"]["status"], "processing")
        self.assertEqual(second_response.json()["ticket_event"]["event_id"], first_response.json()["ticket_event"]["event_id"])

        ticket = self.client.get(f"/api/tickets/{self.ticket_id}").json()
        self.assertEqual(len(ticket["events"]), 1)

    def test_callback_rejects_invalid_transition(self) -> None:
        response = self.callback("resolve", "FEISHU-EVENT-005")

        self.assertEqual(response.status_code, 409)
        self.assertIn("cannot transition", response.json()["detail"])

        with SessionLocal() as db:
            from models.feishu_event import FeishuEvent

            self.assertIsNone(db.get(FeishuEvent, "FEISHU-EVENT-005"))

    def test_callback_rejects_unknown_action_and_ticket(self) -> None:
        unknown_action = self.callback("ignore", "FEISHU-EVENT-006")
        self.assertEqual(unknown_action.status_code, 422)

        response = self.client.post(
            "/api/feishu/callback",
            json={
                "event_id": "FEISHU-EVENT-007",
                "ticket_id": "TCK-NOT-FOUND",
                "action": "claim",
                "operator": "客服A",
            },
        )
        self.assertEqual(response.status_code, 404)
