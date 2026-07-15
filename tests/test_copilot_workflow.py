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
from services.redis_service import RedisService, RedisStatus
from services.session_memory_service import SessionContext
from schemas.copilot import CopilotHistoryMessage


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

    def test_workflow_uses_redis_session_context_when_followup_has_no_order_id(self) -> None:
        payload = CopilotAnalyzeRequest(
            session_id="SESSION-REDIS-CONTEXT-001",
            user_id="USER-001",
            user_message="请继续帮我催一下物流。",
        )
        session_context = SessionContext(
            messages=[CopilotHistoryMessage(role="user", content="订单 ORD-1001 一直没收到。")],
            order_id="ORD-1001",
        )

        with patch.dict("os.environ", {"FEISHU_WEBHOOK_URL": ""}), SessionLocal() as db:
            run = start_agent_run(
                db,
                session_id=payload.session_id,
                user_id=payload.user_id,
                user_message=payload.user_message,
            )
            state = run_copilot_workflow(
                db=db,
                payload=payload,
                run_id=run.run_id,
                session_context=session_context,
            )

        self.assertEqual(state.order_id, "ORD-1001")

    def test_second_run_records_rag_cache_hits(self) -> None:
        from services.rag_cache_service import RagCache

        class FakeRedisClient:
            def __init__(self) -> None:
                self.values: dict[str, str] = {}

            def get(self, key: str) -> str | None:
                return self.values.get(key)

            def set(self, key: str, value: str, ex: int | None = None) -> bool:
                self.values[key] = value
                return True

        cache = RagCache(
            redis_service=RedisService(FakeRedisClient(), RedisStatus("connected", "available")),
            ttl_seconds=300,
        )
        payload = CopilotAnalyzeRequest(
            session_id="SESSION-RAG-CACHE-001",
            user_id="USER-001",
            user_message="我的订单 ORD-1001 怎么还没收到？",
        )

        with patch("services.rag_cache_service.RagCache.from_environment", return_value=cache), patch.dict(
            "os.environ", {"FEISHU_WEBHOOK_URL": ""}
        ), SessionLocal() as db:
            first_run = start_agent_run(db, session_id=payload.session_id, user_id=payload.user_id, user_message=payload.user_message)
            run_copilot_workflow(db=db, payload=payload, run_id=first_run.run_id)
            second_run = start_agent_run(db, session_id=payload.session_id, user_id=payload.user_id, user_message=payload.user_message)
            second_state = run_copilot_workflow(db=db, payload=payload, run_id=second_run.run_id)
            second_rag_cache_hits = [
                step.cache_hit
                for step in second_state.steps
                if step.step_name in {"query_rewrite", "policy_retrieval", "policy_rerank"}
            ]

        self.assertEqual(second_rag_cache_hits, [True, True, True])

    def test_reused_ticket_does_not_send_a_second_feishu_notification(self) -> None:
        payload = CopilotAnalyzeRequest(
            session_id="SESSION-WORKFLOW-TICKET-REUSE-001",
            user_id="USER-001",
            user_message="订单 ORD-1001 一直没收到，帮我催物流。",
        )

        with patch("agents.nodes.feishu_notify_node.send_feishu_text_notification") as send_notification, SessionLocal() as db:
            send_notification.return_value.status = "success"
            send_notification.return_value.message = "Feishu webhook sent"
            first_run = start_agent_run(db, session_id=payload.session_id, user_id=payload.user_id, user_message=payload.user_message)
            first_state = run_copilot_workflow(db=db, payload=payload, run_id=first_run.run_id)
            second_run = start_agent_run(db, session_id=payload.session_id, user_id=payload.user_id, user_message=payload.user_message)
            second_state = run_copilot_workflow(db=db, payload=payload, run_id=second_run.run_id)

        self.assertTrue(first_state.ticket_created)
        self.assertFalse(second_state.ticket_created)
        self.assertTrue(second_state.ticket_reused)
        self.assertEqual(second_state.feishu_status, "skipped")
        self.assertEqual(send_notification.call_count, 1)
