import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from api.main import app
from models.database import SessionLocal
from services.trace_service import finish_agent_run, record_agent_step, start_agent_run


class TestAgentTraceApi(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_run_and_steps_can_be_recorded_and_queried(self) -> None:
        with SessionLocal() as db:
            run = start_agent_run(
                db,
                session_id="SESSION-TRACE-001",
                user_id="USER-001",
                user_message="我的订单 ORD-1001 怎么还没收到？",
                intent="logistics_delay",
            )
            record_agent_step(
                db,
                run_id=run.run_id,
                step_name="intent_recognition",
                step_type="agent",
                status="success",
                input_summary="用户反馈订单未收到",
                output_summary="识别为物流催单场景",
            )
            record_agent_step(
                db,
                run_id=run.run_id,
                step_name="logistics_check",
                step_type="tool",
                status="success",
                input_summary="查询 ORD-1001 物流",
                output_summary="物流超过 72 小时未更新",
                cache_hit=True,
            )
            finish_agent_run(db, run_id=run.run_id, status="success")
            run_id = run.run_id

        run_response = self.client.get(f"/api/runs/{run_id}")
        self.assertEqual(run_response.status_code, 200)
        run_body = run_response.json()
        self.assertEqual(run_body["run_id"], run_id)
        self.assertEqual(run_body["session_id"], "SESSION-TRACE-001")
        self.assertEqual(run_body["user_id"], "USER-001")
        self.assertEqual(run_body["intent"], "logistics_delay")
        self.assertEqual(run_body["status"], "success")
        self.assertIsNotNone(run_body["finished_at"])
        self.assertIsInstance(run_body["total_duration_ms"], int)

        steps_response = self.client.get(f"/api/runs/{run_id}/steps")
        self.assertEqual(steps_response.status_code, 200)
        steps_body = steps_response.json()
        self.assertEqual(len(steps_body), 2)
        self.assertEqual(steps_body[0]["step_name"], "intent_recognition")
        self.assertEqual(steps_body[0]["step_type"], "agent")
        self.assertEqual(steps_body[0]["status"], "success")
        self.assertIsInstance(steps_body[0]["duration_ms"], int)
        self.assertEqual(steps_body[1]["step_name"], "logistics_check")
        self.assertTrue(steps_body[1]["cache_hit"])

    def test_unknown_run_returns_404(self) -> None:
        response = self.client.get("/api/runs/RUN-NOT-FOUND")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Agent run not found")

    def test_runs_can_be_listed_newest_first(self) -> None:
        with SessionLocal() as db:
            first_run = start_agent_run(
                db,
                session_id="SESSION-LIST-001",
                user_id="USER-001",
                user_message="订单 ORD-1001 还没收到",
                intent="logistics_delay",
            )
            finish_agent_run(db, run_id=first_run.run_id, status="success")
            second_run = start_agent_run(
                db,
                session_id="SESSION-LIST-002",
                user_id="USER-002",
                user_message="订单 ORD-1002 到哪里了？",
                intent="logistics_query",
            )
            finish_agent_run(db, run_id=second_run.run_id, status="success")
            first_run_id = first_run.run_id
            second_run_id = second_run.run_id

        response = self.client.get("/api/runs")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([run["run_id"] for run in body], [second_run_id, first_run_id])
        self.assertEqual(body[0]["user_message"], "订单 ORD-1002 到哪里了？")
        self.assertEqual(body[0]["intent"], "logistics_query")

    def test_runs_can_be_filtered_by_run_ticket_or_order_id(self) -> None:
        with SessionLocal() as db:
            run = start_agent_run(
                db,
                session_id="SESSION-SEARCH-001",
                user_id="USER-001",
                user_message="订单 ORD-1001 还没收到",
            )
            run.order_id = "ORD-1001"
            db.commit()
            run_id = run.run_id

        self.assertEqual(self.client.get(f"/api/runs?q={run_id}").json()[0]["run_id"], run_id)
        self.assertEqual(self.client.get("/api/runs?q=ORD-1001").json()[0]["run_id"], run_id)

    def test_demo_waterfall_run_has_proportional_step_durations(self) -> None:
        response = self.client.post("/api/runs/demo-waterfall")

        self.assertEqual(response.status_code, 201)
        run_body = response.json()
        self.assertTrue(run_body["run_id"].startswith("RUN-DEMO-"))
        self.assertEqual(run_body["user_message"], "瀑布图示范链路：订单 ORD-1001 未收到")
        self.assertEqual(run_body["status"], "success")
        self.assertEqual(run_body["total_duration_ms"], 1745)

        steps_response = self.client.get(f"/api/runs/{run_body['run_id']}/steps")

        self.assertEqual(steps_response.status_code, 200)
        steps_body = steps_response.json()
        self.assertEqual(
            [step["step_name"] for step in steps_body],
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
        self.assertEqual(
            [step["duration_ms"] for step in steps_body],
            [55, 20, 85, 120, 45, 130, 620, 340, 120, 90, 120],
        )
        self.assertEqual(steps_body[6]["step_type"], "rag")
        self.assertEqual(steps_body[6]["status"], "success")
