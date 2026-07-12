import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.database import SessionLocal
from schemas.copilot import CopilotAnalyzeRequest
from services.trace_service import finish_agent_run, start_agent_run
from agents.state import CopilotState
from agents.workflow import build_copilot_graph, run_copilot_workflow


class TestCopilotWorkflow(unittest.TestCase):
    def test_workflow_builds_langgraph_app(self) -> None:
        graph = build_copilot_graph()
        self.assertTrue(hasattr(graph, "invoke"))

    def test_workflow_executes_nodes_and_returns_state(self) -> None:
        payload = CopilotAnalyzeRequest(
            session_id="SESSION-WORKFLOW-001",
            user_id="USER-001",
            user_message="我的订单 ORD-1001 怎么还没收到？",
        )

        with patch.dict("os.environ", {"FEISHU_WEBHOOK_URL": ""}), SessionLocal() as db:
            run = start_agent_run(
                db,
                session_id=payload.session_id,
                user_id=payload.user_id,
                user_message=payload.user_message,
            )
            state = run_copilot_workflow(db=db, payload=payload, run_id=run.run_id)
            finish_agent_run(db, run_id=run.run_id, status="success")

            self.assertEqual(state.intent, "logistics_delay")
            self.assertEqual(state.order_id, "ORD-1001")
            self.assertTrue(state.is_abnormal)
            self.assertIsNotNone(state.ticket_id)
            self.assertEqual(state.feishu_status, "disabled")
            self.assertGreaterEqual(len(state.retrieved_policies), 1)
            self.assertIn("物流超过 72 小时未更新", state.reply_draft)

            step_names = [step.step_name for step in state.steps]
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

    def test_langgraph_app_executes_nodes(self) -> None:
        payload = CopilotAnalyzeRequest(
            session_id="SESSION-LANGGRAPH-001",
            user_id="USER-001",
            user_message="我的订单 ORD-1001 怎么还没收到？",
        )

        with patch.dict("os.environ", {"FEISHU_WEBHOOK_URL": ""}), SessionLocal() as db:
            run = start_agent_run(
                db,
                session_id=payload.session_id,
                user_id=payload.user_id,
                user_message=payload.user_message,
            )
            graph = build_copilot_graph()
            state = graph.invoke(CopilotState(payload=payload, run_id=run.run_id, db=db))
            finish_agent_run(db, run_id=run.run_id, status="success")

            self.assertEqual(state.intent, "logistics_delay")
            self.assertEqual(state.order_id, "ORD-1001")
            self.assertTrue(state.is_abnormal)
            self.assertIsNotNone(state.ticket_id)
            self.assertEqual(state.feishu_status, "disabled")
            self.assertGreaterEqual(len(state.retrieved_policies), 1)
            self.assertEqual(state.steps[-1].step_name, "feishu_notify")
