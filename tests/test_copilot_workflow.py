import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import func, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.database import SessionLocal
from models.business import TicketEvent
from schemas.copilot import CopilotAnalyzeRequest
from services.trace_service import finish_agent_run, start_agent_run
from agents.state import CopilotState
from agents.nodes.reply_generate_node import has_unresolved_placeholder
from agents.workflow import build_copilot_graph, run_copilot_workflow
from services.redis_service import RedisService, RedisStatus
from services.session_memory_service import SessionContext
from schemas.copilot import CopilotHistoryMessage


class TestCopilotWorkflow(unittest.TestCase):
    def test_reply_placeholder_detection_flags_unfinished_llm_drafts(self) -> None:
        self.assertTrue(has_unresolved_placeholder("您的订单已于【签收时间】签收。"))
        self.assertTrue(has_unresolved_placeholder("您的订单已于[时间]签收。"))
        self.assertFalse(has_unresolved_placeholder("您的订单物流状态正常，请您确认查收。"))

    def test_workflow_builds_langgraph_app(self) -> None:
        graph = build_copilot_graph()
        self.assertTrue(hasattr(graph, "invoke"))

    def test_workflow_executes_nodes_and_returns_state(self) -> None:
        payload = CopilotAnalyzeRequest(
            session_id="SESSION-WORKFLOW-001",
            user_id="USER-001",
            user_message="我的订单 ORD-1001 怎么还没收到？帮我催一下物流。",
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
            self.assertFalse(state.approval_required)
            self.assertEqual(state.approval_status, "not_required")
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

    def test_langgraph_app_executes_nodes(self) -> None:
        payload = CopilotAnalyzeRequest(
            session_id="SESSION-LANGGRAPH-001",
            user_id="USER-001",
            user_message="我的订单 ORD-1001 怎么还没收到？帮我催一下物流。",
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
            second_payload = CopilotAnalyzeRequest(
                session_id=payload.session_id,
                user_id=payload.user_id,
                user_message="订单 ORD-1001 的物流现在进展怎么样？",
            )
            second_run = start_agent_run(
                db,
                session_id=second_payload.session_id,
                user_id=second_payload.user_id,
                user_message=second_payload.user_message,
            )
            second_state = run_copilot_workflow(
                db=db,
                payload=second_payload,
                run_id=second_run.run_id,
            )
            followup_event_count = db.scalar(
                select(func.count(TicketEvent.event_id)).where(
                    TicketEvent.ticket_id == first_state.ticket_id,
                    TicketEvent.event_type == "copilot_followup_analyzed",
                )
            )

        self.assertTrue(first_state.ticket_created)
        self.assertFalse(second_state.ticket_created)
        self.assertFalse(second_state.ticket_reused)
        self.assertEqual(first_state.ticket_association, "created")
        self.assertEqual(second_state.ticket_association, "session_linked")
        self.assertEqual(second_state.ticket_id, first_state.ticket_id)
        self.assertEqual(followup_event_count, 0)
        self.assertEqual(second_state.feishu_status, "skipped")
        self.assertEqual(send_notification.call_count, 1)

    def test_approval_workflow_sends_review_card_with_app_bot(self) -> None:
        payload = CopilotAnalyzeRequest(
            session_id="SESSION-WORKFLOW-APP-BOT-001",
            user_id="USER-006",
            user_message="订单 ORD-1006 金额比较高，我想退款。",
        )

        with patch("agents.nodes.feishu_notify_node.send_feishu_app_bot_card_notification") as send_app_bot, patch(
            "agents.nodes.feishu_notify_node.send_feishu_text_notification"
        ) as send_text, patch.dict(
            "os.environ",
            {
                "FEISHU_APP_ID": "cli_demo",
                "FEISHU_APP_SECRET": "secret_demo",
                "FEISHU_CHAT_ID": "oc_demo",
            },
        ), SessionLocal() as db:
            send_app_bot.return_value.status = "success"
            send_app_bot.return_value.message = "Feishu app bot card sent"
            run = start_agent_run(db, session_id=payload.session_id, user_id=payload.user_id, user_message=payload.user_message)
            state = run_copilot_workflow(db=db, payload=payload, run_id=run.run_id)

        self.assertTrue(state.approval_required)
        self.assertEqual(state.approval_status, "pending")
        self.assertEqual(state.feishu_status, "success")
        send_app_bot.assert_called_once()
        send_text.assert_not_called()
        self.assertEqual(state.steps[-1].step_name, "feishu_notify")
        self.assertEqual(state.steps[-1].step_type, "feishu_app_bot")
        self.assertIn("自建应用审核卡片", state.steps[-1].output_summary)

    def test_approval_workflow_falls_back_to_webhook_text_when_app_bot_is_disabled(self) -> None:
        payload = CopilotAnalyzeRequest(
            session_id="SESSION-WORKFLOW-APP-BOT-DISABLED-001",
            user_id="USER-006",
            user_message="订单 ORD-1006 金额比较高，我想退款。",
        )

        with patch("agents.nodes.feishu_notify_node.send_feishu_app_bot_card_notification") as send_app_bot, patch(
            "agents.nodes.feishu_notify_node.send_feishu_text_notification"
        ) as send_text, patch.dict(
            "os.environ",
            {
                "FEISHU_APP_ID": "",
                "FEISHU_APP_SECRET": "",
                "FEISHU_CHAT_ID": "",
                "FEISHU_WEBHOOK_URL": "",
            },
        ), SessionLocal() as db:
            send_app_bot.return_value.status = "disabled"
            send_app_bot.return_value.message = "FEISHU_APP_ID, FEISHU_APP_SECRET, or FEISHU_CHAT_ID is not configured"
            send_text.return_value.status = "disabled"
            send_text.return_value.message = "FEISHU_WEBHOOK_URL is not configured"
            run = start_agent_run(db, session_id=payload.session_id, user_id=payload.user_id, user_message=payload.user_message)
            state = run_copilot_workflow(db=db, payload=payload, run_id=run.run_id)

        self.assertTrue(state.approval_required)
        self.assertEqual(state.feishu_status, "disabled")
        send_app_bot.assert_called_once()
        send_text.assert_called_once()
        self.assertEqual(state.steps[-1].step_name, "feishu_notify")
        self.assertEqual(state.steps[-1].step_type, "webhook")
        self.assertIn("降级为 Webhook 待审核通知", state.steps[-1].output_summary)

    def test_abnormal_logistics_without_explicit_follow_up_does_not_create_ticket(self) -> None:
        payload = CopilotAnalyzeRequest(
            session_id="SESSION-NO-FOLLOWUP",
            user_id="USER-001",
            user_message="订单 ORD-1001 一直没收到。",
        )

        with patch.dict("os.environ", {"FEISHU_WEBHOOK_URL": ""}), SessionLocal() as db:
            run = start_agent_run(
                db,
                session_id=payload.session_id,
                user_id=payload.user_id,
                user_message=payload.user_message,
            )
            state = run_copilot_workflow(db=db, payload=payload, run_id=run.run_id)

        self.assertFalse(state.follow_up_requested)
        self.assertEqual(state.ticket_association, "none")
        self.assertIsNone(state.ticket_id)

    def test_follow_up_request_is_based_on_current_turn_only(self) -> None:
        first_payload = CopilotAnalyzeRequest(
            session_id="SESSION-CURRENT-TURN",
            user_id="USER-001",
            user_message="订单 ORD-1001 没收到，帮我催物流。",
        )
        second_payload = CopilotAnalyzeRequest(
            session_id=first_payload.session_id,
            user_id=first_payload.user_id,
            user_message="订单 ORD-1001 的物流现在怎么样？",
            history=[
                CopilotHistoryMessage(role="user", content=first_payload.user_message),
            ],
        )

        with patch.dict("os.environ", {"FEISHU_WEBHOOK_URL": ""}), SessionLocal() as db:
            first_run = start_agent_run(
                db,
                session_id=first_payload.session_id,
                user_id=first_payload.user_id,
                user_message=first_payload.user_message,
            )
            first_state = run_copilot_workflow(
                db=db,
                payload=first_payload,
                run_id=first_run.run_id,
            )
            second_run = start_agent_run(
                db,
                session_id=second_payload.session_id,
                user_id=second_payload.user_id,
                user_message=second_payload.user_message,
            )
            second_state = run_copilot_workflow(
                db=db,
                payload=second_payload,
                run_id=second_run.run_id,
            )

        self.assertTrue(first_state.follow_up_requested)
        self.assertFalse(second_state.follow_up_requested)
