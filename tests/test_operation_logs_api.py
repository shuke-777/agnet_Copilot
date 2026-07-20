import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app
from models.database import SessionLocal


class TestOperationLogsApi(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_manual_ticket_action_writes_database_and_daily_jsonl_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous_log_dir = os.environ.get("OPERATION_LOG_DIR")
            os.environ["OPERATION_LOG_DIR"] = directory
            try:
                created = self.client.post(
                    "/api/tickets",
                    json={
                        "ticket_type": "logistics_delay",
                        "priority": "high",
                        "user_id": "USER-001",
                        "order_id": "ORD-1001",
                        "summary": "操作日志测试工单。",
                        "suggested_action": "人工跟进。",
                        "created_by": "manual",
                    },
                ).json()
                ticket_id = created["ticket_id"]

                action_response = self.client.post(
                    f"/api/tickets/{ticket_id}/actions",
                    json={"action": "claim", "operator": "客服A"},
                )

                self.assertEqual(action_response.status_code, 200)
                response = self.client.get(
                    "/api/operation-logs",
                    params={"ticket_id": ticket_id, "action": "manual_status_changed"},
                )
                self.assertEqual(response.status_code, 200)
                records = response.json()
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]["operator"], "客服A")
                self.assertEqual(records[0]["target_id"], ticket_id)
                self.assertEqual(records[0]["status"], "success")

                files = list(Path(directory).glob("operation-*.jsonl"))
                self.assertEqual(len(files), 1)
                lines = files[0].read_text(encoding="utf-8").splitlines()
                action_log = next(json.loads(line) for line in lines if ticket_id in line and "manual_status_changed" in line)
                self.assertEqual(action_log["ticket_id"], ticket_id)
                self.assertEqual(action_log["action"], "manual_status_changed")
            finally:
                if previous_log_dir is None:
                    os.environ.pop("OPERATION_LOG_DIR", None)
                else:
                    os.environ["OPERATION_LOG_DIR"] = previous_log_dir

    def test_operation_logs_support_business_correlation_filters(self) -> None:
        with SessionLocal() as db:
            from services.operation_log_service import record_operation_log

            record_operation_log(
                db,
                operator="agent",
                operator_type="agent",
                action="copilot_analyze_completed",
                target_type="agent_run",
                target_id="RUN-OP-001",
                ticket_id="TCK-OP-001",
                run_id="RUN-OP-001",
                order_id="ORD-1001",
                source="copilot",
                status="success",
                summary="Copilot 分析完成。",
            )
            record_operation_log(
                db,
                operator="客服B",
                operator_type="human",
                action="manual_status_changed",
                target_type="ticket",
                target_id="TCK-OP-002",
                ticket_id="TCK-OP-002",
                order_id="ORD-1002",
                source="admin",
                status="success",
                summary="人工领取工单。",
            )
            db.commit()

        response = self.client.get(
            "/api/operation-logs",
            params={
                "run_id": "RUN-OP-001",
                "order_id": "ORD-1001",
                "operator": "agent",
                "status": "success",
            },
        )

        self.assertEqual(response.status_code, 200)
        records = response.json()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["target_id"], "RUN-OP-001")

