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

    def test_unknown_run_returns_404(self) -> None:
        response = self.client.get("/api/runs/RUN-NOT-FOUND")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Agent run not found")
