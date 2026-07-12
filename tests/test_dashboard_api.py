import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from api.business import make_id
from api.main import app
from models.business import Ticket
from models.database import SessionLocal
from services.trace_service import finish_agent_run, record_agent_step, start_agent_run


class TestDashboardApi(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def seed_dashboard_data(self) -> None:
        with SessionLocal() as db:
            db.add_all(
                [
                    Ticket(
                        ticket_id=make_id("TCK"),
                        ticket_type="logistics_delay",
                        priority="high",
                        status="todo",
                        user_id="USER-001",
                        order_id="ORD-1001",
                        summary="待处理异常物流工单",
                        suggested_action="联系承运商",
                        created_by="agent",
                    ),
                    Ticket(
                        ticket_id=make_id("TCK"),
                        ticket_type="logistics_delay",
                        priority="normal",
                        status="resolved",
                        user_id="USER-002",
                        order_id="ORD-1002",
                        summary="已解决物流咨询",
                        suggested_action="无需进一步操作",
                        created_by="agent",
                    ),
                ]
            )
            db.commit()

            run = start_agent_run(
                db,
                session_id="SESSION-DASHBOARD-001",
                user_id="USER-001",
                user_message="订单 ORD-1001 怎么还没收到？",
            )
            record_agent_step(
                db,
                run_id=run.run_id,
                step_name="intent_recognition",
                step_type="agent",
                status="success",
            )
            record_agent_step(
                db,
                run_id=run.run_id,
                step_name="feishu_notify",
                step_type="webhook",
                status="success",
            )
            record_agent_step(
                db,
                run_id=run.run_id,
                step_name="feishu_notify",
                step_type="webhook",
                status="failed",
            )
            finish_agent_run(db, run_id=run.run_id, status="success")

    def test_overview_and_ticket_stats_return_aggregated_metrics(self) -> None:
        self.seed_dashboard_data()

        overview_response = self.client.get("/api/dashboard/overview")
        self.assertEqual(overview_response.status_code, 200)
        overview = overview_response.json()
        self.assertEqual(overview["ticket_total"], 2)
        self.assertEqual(overview["pending_ticket_count"], 1)
        self.assertEqual(overview["high_priority_pending_ticket_count"], 1)
        self.assertEqual(overview["agent_run_total"], 1)
        self.assertEqual(overview["agent_run_success_rate"], 1.0)
        self.assertEqual(overview["feishu_notification_attempt_count"], 2)
        self.assertEqual(overview["feishu_notification_success_rate"], 0.5)

        ticket_response = self.client.get("/api/dashboard/ticket-stats")
        self.assertEqual(ticket_response.status_code, 200)
        ticket_stats = ticket_response.json()
        status_counts = {item["key"]: item["count"] for item in ticket_stats["status_counts"]}
        priority_counts = {item["key"]: item["count"] for item in ticket_stats["priority_counts"]}
        self.assertEqual(status_counts, {"resolved": 1, "todo": 1})
        self.assertEqual(priority_counts, {"high": 1, "normal": 1})

    def test_agent_performance_groups_steps_and_ignores_skipped_feishu_notifications(self) -> None:
        self.seed_dashboard_data()
        with SessionLocal() as db:
            run = start_agent_run(
                db,
                session_id="SESSION-DASHBOARD-002",
                user_message="订单 ORD-1002 的物流正常吗？",
            )
            record_agent_step(
                db,
                run_id=run.run_id,
                step_name="feishu_notify",
                step_type="webhook",
                status="skipped",
            )
            finish_agent_run(db, run_id=run.run_id, status="failed")

        response = self.client.get("/api/dashboard/agent-performance")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["agent_run_total"], 2)
        self.assertEqual(body["agent_run_success_rate"], 0.5)
        step_stats = {item["step_name"]: item for item in body["step_performance"]}
        self.assertEqual(step_stats["intent_recognition"]["success_count"], 1)
        self.assertEqual(step_stats["feishu_notify"]["count"], 3)
        self.assertEqual(step_stats["feishu_notify"]["success_count"], 1)
        self.assertEqual(step_stats["feishu_notify"]["failed_count"], 1)
