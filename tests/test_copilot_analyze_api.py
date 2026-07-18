import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from sqlalchemy import select

from api.main import app
from agents.nodes.intent_node import normalize_intent
from models.agent_trace import AgentRun, AgentStep
from models.business import Logistics, Order, SessionTicketBinding, Ticket
from models.database import SessionLocal
from services.session_memory_service import SessionContext


class TestCopilotAnalyzeApi(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_analyze_start_creates_running_run_before_background_execution(self) -> None:
        with patch("api.copilot.run_after_sales_issue_background"), patch.dict("os.environ", {"FEISHU_WEBHOOK_URL": ""}):
            response = self.client.post(
                "/api/copilot/analyze/start",
                json={
                    "session_id": "SESSION-COPILOT-START-001",
                    "user_id": "USER-001",
                    "user_message": "我的订单 ORD-1001 怎么还没收到？帮我催一下物流。",
                },
            )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], "running")
        self.assertTrue(body["run_id"].startswith("RUN-"))
        self.assertTrue(body["events_url"].endswith(f"/api/runs/{body['run_id']}/events"))

        with SessionLocal() as db:
            run = db.get(AgentRun, body["run_id"])
            self.assertIsNotNone(run)
            self.assertEqual(run.status, "running")
            self.assertIsNone(run.result_payload)

    def test_analyze_creates_ticket_for_abnormal_logistics(self) -> None:
        with patch.dict("os.environ", {"FEISHU_WEBHOOK_URL": ""}):
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
        self.assertEqual(body["ticket_association"], "created")
        self.assertIsNotNone(body["ticket_id"])
        self.assertEqual(body["feishu_status"], "disabled")
        self.assertFalse(body["approval_required"])
        self.assertEqual(body["approval_status"], "not_required")
        self.assertEqual(body["approval_reason"], "物流催办不涉及资金、库存或权益变更")
        self.assertGreaterEqual(len(body["policy_sources"]), 1)
        self.assertEqual(body["policy_sources"][0]["source_id"], "logistics_delay_72h_sop")
        self.assertIn("物流超过 72 小时未更新", body["reply_draft"])
        self.assertIn("处理 SOP", body["reply_draft"])

        ticket_response = self.client.get(f"/api/tickets/{body['ticket_id']}")
        self.assertEqual(ticket_response.status_code, 200)
        ticket = ticket_response.json()
        self.assertEqual(ticket["ticket_type"], "logistics_delay")
        self.assertEqual(ticket["status"], "todo")
        self.assertEqual(ticket["created_by"], "agent")
        self.assertEqual(ticket["source_run_id"], body["run_id"])

        run_response = self.client.get(f"/api/runs/{body['run_id']}")
        self.assertEqual(run_response.status_code, 200)
        self.assertEqual(run_response.json()["order_id"], "ORD-1001")
        self.assertEqual(run_response.json()["ticket_id"], body["ticket_id"])

        steps_response = self.client.get(f"/api/runs/{body['run_id']}/steps")
        self.assertEqual(steps_response.status_code, 200)
        step_names = [step["step_name"] for step in steps_response.json()]
        self.assertEqual(
            step_names,
            [
                "intent_recognition",
                "order_extract",
                "order_query",
                "session_binding_check",
                "logistics_query",
                "abnormal_check",
                "follow_up_check",
                "query_rewrite",
                "policy_retrieval",
                "policy_rerank",
                "reply_generate",
                "approval_check",
                "ticket_create",
                "feishu_notify",
            ],
        )
        feishu_step = steps_response.json()[-1]
        self.assertEqual(feishu_step["step_type"], "webhook")
        self.assertEqual(feishu_step["status"], "skipped")

        intent_step = steps_response.json()[0]
        self.assertEqual(intent_step["llm_provider"], "disabled")
        self.assertEqual(intent_step["llm_model"], None)
        self.assertEqual(intent_step["fallback_reason"], "LLM provider is disabled")

    def test_analyze_does_not_create_ticket_for_normal_logistics(self) -> None:
        with patch.dict("os.environ", {"FEISHU_WEBHOOK_URL": ""}):
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
        self.assertEqual(body["intent"], "logistics_query")
        self.assertFalse(body["is_abnormal"])
        self.assertFalse(body["ticket_created"])
        self.assertEqual(body["ticket_association"], "none")
        self.assertIsNone(body["ticket_id"])
        self.assertEqual(body["feishu_status"], "skipped")
        source_ids = {source["source_id"] for source in body["policy_sources"]}
        self.assertIn("normal_logistics_reply_script", source_ids)
        self.assertIn("物流状态正常", body["reply_draft"])

        steps_response = self.client.get(f"/api/runs/{body['run_id']}/steps")
        self.assertEqual(steps_response.status_code, 200)
        step_names = [step["step_name"] for step in steps_response.json()]
        self.assertNotIn("ticket_create", step_names)
        self.assertIn("feishu_notify", step_names)

    def test_extended_abnormal_logistics_demo_order_creates_ticket(self) -> None:
        with patch.dict("os.environ", {"FEISHU_WEBHOOK_URL": ""}):
            response = self.client.post(
                "/api/copilot/analyze",
                json={
                    "session_id": "SESSION-COPILOT-ORD-1003",
                    "user_id": "USER-003",
                    "user_message": "订单 ORD-1003 物流 96 小时没更新，帮我催一下物流。",
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["order_id"], "ORD-1003")
        self.assertEqual(body["intent"], "logistics_delay")
        self.assertTrue(body["is_abnormal"])
        self.assertTrue(body["ticket_created"])
        self.assertEqual(body["ticket_association"], "created")

    def test_unshipped_and_normal_logistics_demo_orders_do_not_create_logistics_ticket(self) -> None:
        cases = [
            (
                "ORD-1004",
                "USER-004",
                "订单 ORD-1004 已经付款了，什么时候发货？",
                "shipping_timeliness",
            ),
            (
                "ORD-1012",
                "USER-012",
                "订单 ORD-1012 帮我催一下物流，什么时候能到？",
                "logistics_delay",
            ),
        ]

        for order_id, user_id, user_message, expected_intent in cases:
            with self.subTest(order_id=order_id):
                response = self.client.post(
                    "/api/copilot/analyze",
                    json={
                        "session_id": f"SESSION-COPILOT-{order_id}",
                        "user_id": user_id,
                        "user_message": user_message,
                    },
                )

                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertEqual(body["order_id"], order_id)
                self.assertEqual(body["intent"], expected_intent)
                self.assertFalse(body["ticket_created"])
                self.assertEqual(body["ticket_association"], "none")
                self.assertIsNone(body["ticket_id"])

    def test_analyze_uses_refund_policy_and_creates_pending_approval_ticket(self) -> None:
        response = self.client.post(
            "/api/copilot/analyze",
            json={
                "session_id": "SESSION-COPILOT-REFUND-001",
                "user_id": "USER-001",
                "user_message": "订单 ORD-1001 可以退款吗？",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["intent"], "refund")
        self.assertTrue(body["ticket_created"])
        self.assertEqual(body["ticket_association"], "created")
        self.assertIsNotNone(body["ticket_id"])
        self.assertTrue(body["approval_required"])
        self.assertEqual(body["approval_status"], "pending")
        self.assertIn("退款", body["approval_reason"])
        self.assertIn("退款咨询", body["reply_draft"])
        self.assertEqual(body["policy_sources"][0]["source_id"], "refund_processing_rule")

        steps_response = self.client.get(f"/api/runs/{body['run_id']}/steps")
        self.assertEqual(steps_response.status_code, 200)
        step_names = [step["step_name"] for step in steps_response.json()]
        self.assertIn("query_rewrite", step_names)
        self.assertIn("policy_rerank", step_names)
        self.assertIn("approval_check", step_names)
        self.assertIn("ticket_create", step_names)

        ticket_response = self.client.get(f"/api/tickets/{body['ticket_id']}")
        self.assertEqual(ticket_response.status_code, 200)
        ticket = ticket_response.json()
        self.assertEqual(ticket["ticket_type"], "refund_approval")
        self.assertTrue(ticket["approval_required"])
        self.assertEqual(ticket["approval_status"], "pending")

    def test_extended_approval_demo_orders_create_pending_review_tickets(self) -> None:
        cases = [
            ("ORD-1006", "USER-006", "订单 ORD-1006 金额比较高，我想退款。", "refund", "high"),
            ("ORD-1007", "USER-007", "订单 ORD-1007 我想仅退款。", "refund", "medium"),
            ("ORD-1008", "USER-008", "订单 ORD-1008 我想退货。", "return", "high"),
            ("ORD-1009", "USER-009", "订单 ORD-1009 我想换货。", "exchange", "high"),
            ("ORD-1010", "USER-010", "订单 ORD-1010 已经发货了，我想改地址。", "address_change", "medium"),
            ("ORD-1011", "USER-011", "订单 ORD-1011 我想取消订单。", "cancel_order", "high"),
        ]

        for order_id, user_id, user_message, expected_intent, expected_priority in cases:
            with self.subTest(order_id=order_id):
                response = self.client.post(
                    "/api/copilot/analyze",
                    json={
                        "session_id": f"SESSION-COPILOT-APPROVAL-{order_id}",
                        "user_id": user_id,
                        "user_message": user_message,
                    },
                )

                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertEqual(body["order_id"], order_id)
                self.assertEqual(body["intent"], expected_intent)
                self.assertTrue(body["ticket_created"])
                self.assertTrue(body["approval_required"])
                self.assertEqual(body["approval_status"], "pending")

                ticket_response = self.client.get(f"/api/tickets/{body['ticket_id']}")
                self.assertEqual(ticket_response.status_code, 200)
                ticket = ticket_response.json()
                self.assertEqual(ticket["priority"], expected_priority)
                self.assertTrue(ticket["approval_required"])
                self.assertEqual(ticket["approval_status"], "pending")

    def test_llm_intent_bias_does_not_break_logistics_delay_demo(self) -> None:
        intent = normalize_intent(
            "shipping_timeliness",
            "我的订单 ORD-1001 怎么还没收到？帮我催一下物流。",
        )

        self.assertEqual(intent, "logistics_delay")

    def test_analyze_returns_200_when_feishu_webhook_fails(self) -> None:
        with patch.dict("os.environ", {"FEISHU_WEBHOOK_URL": "https://example.invalid/webhook"}):
            with patch("services.feishu_service.urlopen", side_effect=RuntimeError("webhook unavailable")):
                response = self.client.post(
                    "/api/copilot/analyze",
                    json={
                        "session_id": "SESSION-COPILOT-FEISHU-FAILED",
                        "user_id": "USER-001",
                        "user_message": "我的订单 ORD-1001 怎么还没收到？帮我催一下物流。",
                    },
                )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["feishu_status"], "failed")

        steps_response = self.client.get(f"/api/runs/{body['run_id']}/steps")
        self.assertEqual(steps_response.status_code, 200)
        feishu_step = steps_response.json()[-1]
        self.assertEqual(feishu_step["step_name"], "feishu_notify")
        self.assertEqual(feishu_step["status"], "failed")

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

    def test_analyze_returns_429_when_redis_rate_limiter_rejects_request(self) -> None:
        class RejectingRedisClient:
            def __init__(self) -> None:
                self.eval_calls: list[tuple[object, ...]] = []

            def ping(self) -> bool:
                return True

            def eval(self, *args: object) -> list[int]:
                self.eval_calls.append(args)
                return [0, 0, 17]

        redis_client = RejectingRedisClient()
        with patch.dict(
            "os.environ",
            {
                "REDIS_URL": "redis://127.0.0.1:6379/0",
                "COPILOT_RATE_LIMIT_CAPACITY": "10",
                "COPILOT_RATE_LIMIT_WINDOW_SECONDS": "60",
            },
        ), patch("redis.Redis.from_url", return_value=redis_client):
            response = self.client.post(
                "/api/copilot/analyze",
                json={
                    "session_id": "SESSION-COPILOT-RATE-LIMIT-001",
                    "user_id": "USER-RATE-LIMIT-001",
                    "user_message": "订单 ORD-1001 怎么还没收到？",
                },
            )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["retry-after"], "17")
        self.assertEqual(
            response.json(),
            {
                "detail": {
                    "code": "copilot_rate_limited",
                    "message": "Copilot analysis rate limit exceeded",
                    "retry_after_seconds": 17,
                },
            },
        )
        self.assertEqual(redis_client.eval_calls[0][2], "rate_limit:copilot:USER-RATE-LIMIT-001")

    def test_analyze_uses_client_ip_when_rate_limiter_has_no_user_id(self) -> None:
        class RejectingRedisClient:
            def __init__(self) -> None:
                self.eval_calls: list[tuple[object, ...]] = []

            def ping(self) -> bool:
                return True

            def eval(self, *args: object) -> list[int]:
                self.eval_calls.append(args)
                return [0, 0, 1]

        redis_client = RejectingRedisClient()
        with patch.dict("os.environ", {"REDIS_URL": "redis://127.0.0.1:6379/0"}), patch(
            "redis.Redis.from_url",
            return_value=redis_client,
        ):
            response = self.client.post(
                "/api/copilot/analyze",
                json={
                    "session_id": "SESSION-COPILOT-IP-LIMIT-001",
                    "user_message": "订单 ORD-1001 怎么还没收到？",
                },
            )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(redis_client.eval_calls[0][2], "rate_limit:copilot:ip:testclient")

    def test_analyze_uses_recent_session_history_when_message_has_no_order_id(self) -> None:
        session_id = "SESSION-COPILOT-CONTEXT-001"
        first_response = self.client.post(
            "/api/copilot/analyze",
            json={
                "session_id": session_id,
                "user_id": "USER-001",
                "user_message": "订单 ORD-1001 一直没收到。",
            },
        )
        self.assertEqual(first_response.status_code, 200)

        second_response = self.client.post(
            "/api/copilot/analyze",
            json={
                "session_id": session_id,
                "user_id": "USER-001",
                "user_message": "那请继续帮我催一下。",
            },
        )

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.json()["order_id"], "ORD-1001")

    def test_new_session_reuses_open_ticket_for_same_order_and_links_followup_run(self) -> None:
        payload = {
            "session_id": "SESSION-COPILOT-TICKET-REUSE-001",
            "user_id": "USER-001",
            "user_message": "我的订单 ORD-1001 一直没收到，帮我催物流。",
        }

        with patch.dict("os.environ", {"FEISHU_WEBHOOK_URL": ""}):
            first_response = self.client.post("/api/copilot/analyze", json=payload)
            second_response = self.client.post(
                "/api/copilot/analyze",
                json={
                    **payload,
                    "session_id": "SESSION-COPILOT-TICKET-REUSE-002",
                    "user_message": "请继续跟进 ORD-1001 的物流异常。",
                },
            )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        first_body = first_response.json()
        second_body = second_response.json()
        self.assertTrue(first_body["ticket_created"])
        self.assertEqual(first_body["ticket_association"], "created")
        self.assertFalse(first_body["ticket_reused"])
        self.assertFalse(second_body["ticket_created"])
        self.assertTrue(second_body["ticket_reused"])
        self.assertEqual(second_body["ticket_association"], "reused")
        self.assertEqual(second_body["ticket_id"], first_body["ticket_id"])
        self.assertEqual(second_body["feishu_status"], "skipped")

        with SessionLocal() as db:
            tickets = list(db.query(Ticket).filter(Ticket.order_id == "ORD-1001"))
        self.assertEqual(len(tickets), 1)

        ticket_response = self.client.get(f"/api/tickets/{first_body['ticket_id']}")
        self.assertEqual(ticket_response.status_code, 200)
        ticket_body = ticket_response.json()
        events = ticket_body["events"]
        self.assertEqual(events[-1]["event_type"], "copilot_followup_analyzed")
        self.assertIn(second_body["run_id"], events[-1]["content"])
        self.assertEqual(
            {run["run_id"] for run in ticket_body["related_runs"]},
            {first_body["run_id"], second_body["run_id"]},
        )

        followup_run = self.client.get(f"/api/runs/{second_body['run_id']}")
        self.assertEqual(followup_run.status_code, 200)
        self.assertEqual(followup_run.json()["ticket_id"], first_body["ticket_id"])

    def test_same_session_links_ticket_without_duplicate_followup_event(self) -> None:
        first_response = self.client.post(
            "/api/copilot/analyze",
            json={
                "session_id": "SESSION-COPILOT-SESSION-LINK",
                "user_id": "USER-001",
                "user_message": "订单 ORD-1001 没收到，帮我催一下物流。",
            },
        )
        second_response = self.client.post(
            "/api/copilot/analyze",
            json={
                "session_id": "SESSION-COPILOT-SESSION-LINK",
                "user_id": "USER-001",
                "user_message": "ORD-1001 的物流现在进展怎么样？",
            },
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        first_body = first_response.json()
        second_body = second_response.json()
        self.assertEqual(second_body["ticket_association"], "session_linked")
        self.assertFalse(second_body["ticket_created"])
        self.assertFalse(second_body["ticket_reused"])
        self.assertEqual(second_body["ticket_id"], first_body["ticket_id"])

        ticket = self.client.get(f"/api/tickets/{first_body['ticket_id']}").json()
        self.assertFalse(
            any(event["event_type"] == "copilot_followup_analyzed" for event in ticket["events"])
        )

    def test_same_session_cross_order_returns_409_without_side_effects(self) -> None:
        with patch(
            "services.copilot_service.SessionMemoryService.from_environment"
        ) as memory_factory:
            memory = memory_factory.return_value
            memory.get_context.return_value = SessionContext()
            first_response = self.client.post(
                "/api/copilot/analyze",
                json={
                    "session_id": "SESSION-COPILOT-CONFLICT",
                    "user_id": "USER-001",
                    "user_message": "订单 ORD-1001 没收到，帮我催一下物流。",
                },
            )
            conflict_response = self.client.post(
                "/api/copilot/analyze",
                json={
                    "session_id": "SESSION-COPILOT-CONFLICT",
                    "user_id": "USER-001",
                    "user_message": "查一下订单 ORD-1002。",
                },
            )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(conflict_response.status_code, 409)
        self.assertEqual(
            conflict_response.json()["detail"],
            {
                "code": "session_order_mismatch",
                "bound_order_id": "ORD-1001",
                "requested_order_id": "ORD-1002",
            },
        )
        self.assertEqual(memory.append_turn.call_count, 1)

        with SessionLocal() as db:
            binding = db.scalar(
                select(SessionTicketBinding).where(
                    SessionTicketBinding.session_id == "SESSION-COPILOT-CONFLICT",
                    SessionTicketBinding.user_scope == "USER-001",
                )
            )
            failed_run = db.scalar(
                select(AgentRun)
                .where(
                    AgentRun.session_id == "SESSION-COPILOT-CONFLICT",
                    AgentRun.status == "failed",
                )
                .order_by(AgentRun.created_at.desc())
            )
            step_names = list(
                db.scalars(
                    select(AgentStep.step_name)
                    .where(AgentStep.run_id == failed_run.run_id)
                    .order_by(AgentStep.start_time)
                )
            )

        self.assertEqual(binding.ticket_id, first_response.json()["ticket_id"])
        self.assertEqual(
            step_names,
            [
                "intent_recognition",
                "order_extract",
                "order_query",
                "session_binding_check",
            ],
        )

    def test_same_session_id_is_isolated_by_user_scope(self) -> None:
        first_response = self.client.post(
            "/api/copilot/analyze",
            json={
                "session_id": "SESSION-COPILOT-SHARED",
                "user_id": "USER-001",
                "user_message": "订单 ORD-1001 没收到，帮我催一下物流。",
            },
        )
        second_response = self.client.post(
            "/api/copilot/analyze",
            json={
                "session_id": "SESSION-COPILOT-SHARED",
                "user_id": "USER-002",
                "user_message": "查一下订单 ORD-1002 的物流。",
            },
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.json()["order_id"], "ORD-1002")

    def test_anonymous_scope_keeps_stable_session_binding(self) -> None:
        first_response = self.client.post(
            "/api/copilot/analyze",
            json={
                "session_id": "SESSION-COPILOT-ANONYMOUS",
                "user_message": "订单 ORD-1001 没收到，帮我催一下物流。",
            },
        )
        second_response = self.client.post(
            "/api/copilot/analyze",
            json={
                "session_id": "SESSION-COPILOT-ANONYMOUS",
                "user_message": "物流现在进展怎么样？",
            },
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.json()["ticket_association"], "session_linked")
        self.assertEqual(
            second_response.json()["ticket_id"],
            first_response.json()["ticket_id"],
        )

    def test_resolved_ticket_is_replaced_after_new_explicit_follow_up(self) -> None:
        first_response = self.client.post(
            "/api/copilot/analyze",
            json={
                "session_id": "SESSION-COPILOT-RESOLVED",
                "user_id": "USER-001",
                "user_message": "订单 ORD-1001 没收到，帮我催一下物流。",
            },
        )
        first_ticket_id = first_response.json()["ticket_id"]
        self.client.post(
            f"/api/tickets/{first_ticket_id}/actions",
            json={"action": "claim", "operator": "客服A"},
        )
        self.client.post(
            f"/api/tickets/{first_ticket_id}/actions",
            json={"action": "resolve", "operator": "客服A"},
        )

        second_response = self.client.post(
            "/api/copilot/analyze",
            json={
                "session_id": "SESSION-COPILOT-RESOLVED",
                "user_id": "USER-001",
                "user_message": "订单 ORD-1001 还是没收到，请继续催。",
            },
        )

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.json()["ticket_association"], "created")
        self.assertNotEqual(second_response.json()["ticket_id"], first_ticket_id)

    def test_reopened_ticket_becomes_active_session_ticket_again(self) -> None:
        first_response = self.client.post(
            "/api/copilot/analyze",
            json={
                "session_id": "SESSION-COPILOT-REOPENED",
                "user_id": "USER-001",
                "user_message": "订单 ORD-1001 没收到，帮我催一下物流。",
            },
        )
        ticket_id = first_response.json()["ticket_id"]
        for action in ("claim", "resolve", "reopen"):
            transition = self.client.post(
                f"/api/tickets/{ticket_id}/actions",
                json={"action": action, "operator": "客服A"},
            )
            self.assertEqual(transition.status_code, 200)

        followup_response = self.client.post(
            "/api/copilot/analyze",
            json={
                "session_id": "SESSION-COPILOT-REOPENED",
                "user_id": "USER-001",
                "user_message": "订单 ORD-1001 的物流现在怎么样？",
            },
        )

        self.assertEqual(followup_response.status_code, 200)
        self.assertEqual(followup_response.json()["ticket_association"], "session_linked")
        self.assertEqual(followup_response.json()["ticket_id"], ticket_id)

    def test_unshipped_order_does_not_create_logistics_delay_ticket(self) -> None:
        with SessionLocal() as db:
            db.add_all(
                [
                    Order(
                        order_id="ORD-1999",
                        user_id="USER-1999",
                        product_name="待发货测试商品",
                        amount=49.0,
                        status="paid",
                    ),
                    Logistics(
                        logistics_id="LOG-1999",
                        order_id="ORD-1999",
                        carrier="测试快递",
                        tracking_no="TEST1999",
                        status="stalled",
                        last_event="测试异常物流事件",
                        last_event_time=datetime(2026, 7, 17, 12, 0, 0),
                        is_abnormal=True,
                    ),
                ]
            )
            db.commit()

        response = self.client.post(
            "/api/copilot/analyze",
            json={
                "session_id": "SESSION-COPILOT-UNSHIPPED",
                "user_id": "USER-1999",
                "user_message": "订单 ORD-1999 的物流异常，帮我催一下。",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ticket_association"], "none")
        self.assertIsNone(response.json()["ticket_id"])

    def test_failed_cross_order_run_is_ignored_by_order_history_fallback(self) -> None:
        first_response = self.client.post(
            "/api/copilot/analyze",
            json={
                "session_id": "SESSION-COPILOT-HISTORY-CONFLICT",
                "user_id": "USER-001",
                "user_message": "订单 ORD-1001 没收到，帮我催一下物流。",
            },
        )
        conflict_response = self.client.post(
            "/api/copilot/analyze",
            json={
                "session_id": "SESSION-COPILOT-HISTORY-CONFLICT",
                "user_id": "USER-001",
                "user_message": "查订单 ORD-1002。",
            },
        )
        followup_response = self.client.post(
            "/api/copilot/analyze",
            json={
                "session_id": "SESSION-COPILOT-HISTORY-CONFLICT",
                "user_id": "USER-001",
                "user_message": "物流现在进展怎么样？",
            },
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(conflict_response.status_code, 409)
        self.assertEqual(followup_response.status_code, 200)
        self.assertEqual(followup_response.json()["order_id"], "ORD-1001")
        self.assertEqual(followup_response.json()["ticket_association"], "session_linked")
