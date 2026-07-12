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


class TestAdminPages(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_ticket_list_page_shows_ticket_table(self) -> None:
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
        ticket_id = create_response.json()["ticket_id"]

        response = self.client.get("/admin/tickets")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("客服工单", response.text)
        self.assertIn(ticket_id, response.text)
        self.assertIn("ORD-1001", response.text)
        self.assertIn("logistics_delay", response.text)

    def test_ticket_detail_page_shows_order_logistics_and_events(self) -> None:
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
        ticket_id = create_response.json()["ticket_id"]
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

        response = self.client.get(f"/admin/tickets/{ticket_id}")

        self.assertEqual(response.status_code, 200)
        self.assertIn("工单详情", response.text)
        self.assertIn(ticket_id, response.text)
        self.assertIn("无线蓝牙耳机", response.text)
        self.assertIn("物流超过 72 小时未更新", response.text)
        self.assertIn("已联系承运商", response.text)

    def test_run_detail_page_shows_agent_steps(self) -> None:
        with SessionLocal() as db:
            run = start_agent_run(
                db,
                session_id="SESSION-ADMIN-001",
                user_id="USER-001",
                user_message="我的订单 ORD-1001 怎么还没收到？",
                intent="logistics_delay",
            )
            record_agent_step(
                db,
                run_id=run.run_id,
                step_name="policy_retrieval",
                step_type="retrieval",
                status="success",
                input_summary="查询售后 SOP",
                output_summary="召回物流超过 72 小时未更新处理 SOP",
            )
            record_agent_step(
                db,
                run_id=run.run_id,
                step_name="feishu_notify",
                step_type="webhook",
                status="skipped",
                input_summary="尝试发送飞书通知",
                output_summary="未配置 FEISHU_WEBHOOK_URL",
            )
            finish_agent_run(db, run_id=run.run_id, status="success")
            run_id = run.run_id

        response = self.client.get(f"/admin/runs/{run_id}")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Agent Run", response.text)
        self.assertIn(run_id, response.text)
        self.assertIn("policy_retrieval", response.text)
        self.assertIn("feishu_notify", response.text)
        self.assertIn("未配置 FEISHU_WEBHOOK_URL", response.text)

    def test_dashboard_page_shows_operational_metrics_and_step_performance(self) -> None:
        create_response = self.client.post(
            "/api/tickets",
            json={
                "ticket_type": "logistics_delay",
                "priority": "high",
                "user_id": "USER-001",
                "order_id": "ORD-1001",
                "summary": "待处理异常物流工单。",
                "suggested_action": "联系承运商。",
                "created_by": "agent",
            },
        )
        self.assertEqual(create_response.status_code, 201)

        with SessionLocal() as db:
            run = start_agent_run(
                db,
                session_id="SESSION-ADMIN-DASHBOARD-001",
                user_message="订单 ORD-1001 怎么还没收到？",
            )
            record_agent_step(
                db,
                run_id=run.run_id,
                step_name="policy_rerank",
                step_type="rag",
                status="success",
            )
            finish_agent_run(db, run_id=run.run_id, status="success")

        response = self.client.get("/admin/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn("运营看板", response.text)
        self.assertIn("待处理工单", response.text)
        self.assertIn("飞书通知成功率", response.text)
        self.assertIn("工单状态分布", response.text)
        self.assertIn("Agent Step 性能", response.text)
        self.assertIn("policy_rerank", response.text)

    def test_ticket_list_page_filters_by_status_and_priority(self) -> None:
        high_ticket = self.client.post(
            "/api/tickets",
            json={
                "ticket_type": "logistics_delay",
                "priority": "high",
                "user_id": "USER-001",
                "order_id": "ORD-1001",
                "summary": "高优先级待处理工单",
                "suggested_action": "联系承运商。",
                "created_by": "agent",
            },
        ).json()
        self.client.post(
            "/api/tickets",
            json={
                "ticket_type": "logistics_delay",
                "priority": "normal",
                "user_id": "USER-002",
                "order_id": "ORD-1002",
                "summary": "普通优先级工单",
                "suggested_action": "等待用户反馈。",
                "created_by": "agent",
            },
        )

        response = self.client.get("/admin/tickets?status=todo&priority=high")

        self.assertEqual(response.status_code, 200)
        self.assertIn("工单筛选", response.text)
        self.assertIn(high_ticket["ticket_id"], response.text)
        self.assertIn("高优先级待处理工单", response.text)
        self.assertNotIn("普通优先级工单", response.text)

    def test_ticket_detail_page_allows_manual_status_actions(self) -> None:
        create_response = self.client.post(
            "/api/tickets",
            json={
                "ticket_type": "logistics_delay",
                "priority": "high",
                "user_id": "USER-001",
                "order_id": "ORD-1001",
                "summary": "需要人工接单的工单",
                "suggested_action": "联系承运商。",
                "created_by": "agent",
            },
        )
        ticket_id = create_response.json()["ticket_id"]

        claim_response = self.client.post(
            f"/admin/tickets/{ticket_id}/actions/claim",
            data={"operator": "客服B"},
            follow_redirects=False,
        )
        self.assertEqual(claim_response.status_code, 303)

        ticket = self.client.get(f"/api/tickets/{ticket_id}").json()
        self.assertEqual(ticket["status"], "processing")
        self.assertEqual(ticket["assigned_to"], "客服B")
        self.assertEqual(ticket["events"][-1]["event_type"], "manual_status_changed")
        self.assertIn("后台人工操作", ticket["events"][-1]["content"])

        resolve_response = self.client.post(
            f"/admin/tickets/{ticket_id}/actions/resolve",
            data={"operator": "客服B"},
            follow_redirects=False,
        )
        reopen_response = self.client.post(
            f"/admin/tickets/{ticket_id}/actions/reopen",
            data={"operator": "客服C"},
            follow_redirects=False,
        )
        self.assertEqual(resolve_response.status_code, 303)
        self.assertEqual(reopen_response.status_code, 303)

        updated_ticket = self.client.get(f"/api/tickets/{ticket_id}").json()
        self.assertEqual(updated_ticket["status"], "processing")
        self.assertEqual(updated_ticket["assigned_to"], "客服C")
