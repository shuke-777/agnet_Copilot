import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from api.main import app
from models.business import Ticket
from models.database import SessionLocal


class TestCopilotAnalyzeApi(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

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
        self.assertIsNotNone(body["ticket_id"])
        self.assertEqual(body["feishu_status"], "disabled")
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
                "logistics_query",
                "abnormal_check",
                "query_rewrite",
                "policy_retrieval",
                "policy_rerank",
                "reply_generate",
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
        self.assertFalse(body["is_abnormal"])
        self.assertFalse(body["ticket_created"])
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

    def test_analyze_uses_refund_policy_without_creating_logistics_ticket(self) -> None:
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
        self.assertFalse(body["ticket_created"])
        self.assertIsNone(body["ticket_id"])
        self.assertIn("退款咨询", body["reply_draft"])
        self.assertEqual(body["policy_sources"][0]["source_id"], "refund_processing_rule")

        steps_response = self.client.get(f"/api/runs/{body['run_id']}/steps")
        self.assertEqual(steps_response.status_code, 200)
        step_names = [step["step_name"] for step in steps_response.json()]
        self.assertIn("query_rewrite", step_names)
        self.assertIn("policy_rerank", step_names)
        self.assertNotIn("ticket_create", step_names)

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

    def test_analyze_reuses_open_ticket_for_same_order_and_links_followup_run(self) -> None:
        payload = {
            "session_id": "SESSION-COPILOT-TICKET-REUSE-001",
            "user_id": "USER-001",
            "user_message": "我的订单 ORD-1001 一直没收到，帮我催物流。",
        }

        with patch.dict("os.environ", {"FEISHU_WEBHOOK_URL": ""}):
            first_response = self.client.post("/api/copilot/analyze", json=payload)
            second_response = self.client.post(
                "/api/copilot/analyze",
                json={**payload, "user_message": "请继续跟进 ORD-1001 的物流异常。"},
            )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        first_body = first_response.json()
        second_body = second_response.json()
        self.assertTrue(first_body["ticket_created"])
        self.assertFalse(first_body["ticket_reused"])
        self.assertFalse(second_body["ticket_created"])
        self.assertTrue(second_body["ticket_reused"])
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
