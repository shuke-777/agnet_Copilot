import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.business import Logistics, Order, Ticket
from services.feishu_service import (
    build_feishu_approval_card_payload,
    build_feishu_approval_message,
    build_feishu_ticket_message,
    send_feishu_app_bot_card_notification,
    send_feishu_card_notification,
    send_feishu_text_notification,
)


class TestFeishuService(unittest.TestCase):
    def test_send_returns_disabled_when_webhook_is_not_configured(self) -> None:
        with patch.dict(os.environ, {"FEISHU_WEBHOOK_URL": ""}):
            result = send_feishu_text_notification("test message")

        self.assertEqual(result.status, "disabled")

    def test_send_returns_failed_when_webhook_request_fails(self) -> None:
        with patch.dict(os.environ, {"FEISHU_WEBHOOK_URL": "https://example.invalid/webhook"}):
            with patch("services.feishu_service.urlopen", side_effect=URLError("network down")):
                result = send_feishu_text_notification("test message")

        self.assertEqual(result.status, "failed")
        self.assertIn("network down", result.message)

    def test_ticket_message_contains_order_ticket_priority_and_summary(self) -> None:
        order = Order(order_id="ORD-1001", user_id="USER-001", product_name="无线蓝牙耳机", amount=199.0, status="shipped")
        logistics = Logistics(
            logistics_id="LOG-1001",
            order_id="ORD-1001",
            carrier="顺丰速运",
            tracking_no="SF1001001001",
            status="stalled",
            last_event="物流超过 72 小时未更新，疑似运输异常。",
            is_abnormal=True,
        )
        ticket = Ticket(
            ticket_id="TCK-1001",
            ticket_type="logistics_delay",
            priority="high",
            status="todo",
            user_id="USER-001",
            order_id="ORD-1001",
            summary="用户反馈订单 ORD-1001 未收到，物流疑似异常。",
            suggested_action="联系承运商核实物流卡点。",
            created_by="agent",
        )

        message = build_feishu_ticket_message(ticket=ticket, order=order, logistics=logistics)

        self.assertIn("ORD-1001", message)
        self.assertIn("TCK-1001", message)
        self.assertIn("high", message)
        self.assertIn("用户反馈订单 ORD-1001 未收到", message)

    def test_approval_message_marks_pending_review_reason(self) -> None:
        order = Order(order_id="ORD-1001", user_id="USER-001", product_name="无线蓝牙耳机", amount=199.0, status="shipped")

        message = build_feishu_approval_message(
            order=order,
            response_level="高",
            applicant="agent",
            approval_reason="退款涉及资金动作，需要人工审核",
            suggested_action="请审核是否允许为订单 ORD-1001 发起退款处理。",
        )

        self.assertIn("【售后处理待审核】", message)
        self.assertIn("响应等级：高", message)
        self.assertIn("订单ID：ORD-1001", message)
        self.assertIn("申请人：agent", message)
        self.assertIn("退款涉及资金动作", message)

    def test_approval_card_contains_buttons_and_ticket_context(self) -> None:
        order = Order(order_id="ORD-1001", user_id="USER-001", product_name="无线蓝牙耳机", amount=199.0, status="shipped")
        ticket = Ticket(
            ticket_id="TCK-REVIEW-001",
            ticket_type="refund_approval",
            priority="high",
            status="todo",
            user_id="USER-001",
            order_id="ORD-1001",
            summary="用户申请订单 ORD-1001 退款，需要人工审核。",
            suggested_action="请审核是否允许为订单 ORD-1001 发起退款处理。",
            created_by="agent",
            approval_required=True,
            approval_status="pending",
            approval_reason="退款涉及资金动作，需要人工审核",
        )

        payload = build_feishu_approval_card_payload(
            ticket=ticket,
            order=order,
            applicant="agent",
            approval_reason=ticket.approval_reason,
            suggested_action=ticket.suggested_action,
        )

        self.assertEqual(payload["msg_type"], "interactive")
        self.assertIn("售后处理待审核", str(payload))
        self.assertIn("TCK-REVIEW-001", str(payload))
        self.assertIn("approve", str(payload))
        self.assertIn("reject", str(payload))
        self.assertIn("manual_confirm", str(payload))

    def test_send_card_uses_interactive_payload(self) -> None:
        payload = {"msg_type": "interactive", "card": {"header": {"title": {"content": "测试"}}}}
        with patch.dict(os.environ, {"FEISHU_WEBHOOK_URL": "https://example.invalid/webhook"}):
            with patch("services.feishu_service.urlopen") as mocked_urlopen:
                mocked_urlopen.return_value.__enter__.return_value.status = 200
                result = send_feishu_card_notification(payload)

        self.assertEqual(result.status, "success")
        request = mocked_urlopen.call_args.args[0]
        self.assertIn('"msg_type": "interactive"', request.data.decode("utf-8"))

    def test_app_bot_card_returns_disabled_when_config_is_missing(self) -> None:
        payload = {"msg_type": "interactive", "card": {"header": {"title": {"content": "测试"}}}}
        with patch.dict(os.environ, {"FEISHU_APP_ID": "", "FEISHU_APP_SECRET": "", "FEISHU_CHAT_ID": ""}):
            result = send_feishu_app_bot_card_notification(payload)

        self.assertEqual(result.status, "disabled")
        self.assertIn("FEISHU_APP_ID", result.message)

    def test_app_bot_card_fetches_token_and_sends_message_to_chat(self) -> None:
        payload = {"msg_type": "interactive", "card": {"header": {"title": {"content": "测试"}}}}

        def fake_urlopen(request, timeout=3.0):
            class FakeResponse:
                status = 200

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return None

                def read(self):
                    if "tenant_access_token" in request.full_url:
                        return b'{"code":0,"msg":"ok","tenant_access_token":"tenant-token"}'
                    return b'{"code":0,"msg":"success","data":{"message_id":"om_demo"}}'

            return FakeResponse()

        with patch.dict(
            os.environ,
            {
                "FEISHU_APP_ID": "cli_demo",
                "FEISHU_APP_SECRET": "secret_demo",
                "FEISHU_CHAT_ID": "oc_demo",
            },
        ):
            with patch("services.feishu_service.urlopen", side_effect=fake_urlopen) as mocked_urlopen:
                result = send_feishu_app_bot_card_notification(payload)

        self.assertEqual(result.status, "success")
        token_request = mocked_urlopen.call_args_list[0].args[0]
        message_request = mocked_urlopen.call_args_list[1].args[0]
        self.assertIn("/auth/v3/tenant_access_token/internal", token_request.full_url)
        self.assertIn("/im/v1/messages?receive_id_type=chat_id", message_request.full_url)
        self.assertEqual(message_request.headers["Authorization"], "Bearer tenant-token")
        message_body = json.loads(message_request.data.decode("utf-8"))
        self.assertEqual(message_body["receive_id"], "oc_demo")
        self.assertEqual(message_body["msg_type"], "interactive")
        self.assertIn("测试", message_body["content"])

    def test_app_bot_card_returns_failed_when_token_request_fails(self) -> None:
        payload = {"msg_type": "interactive", "card": {"header": {"title": {"content": "测试"}}}}

        with patch.dict(
            os.environ,
            {
                "FEISHU_APP_ID": "cli_demo",
                "FEISHU_APP_SECRET": "secret_demo",
                "FEISHU_CHAT_ID": "oc_demo",
            },
        ):
            with patch("services.feishu_service.urlopen", side_effect=URLError("token down")):
                result = send_feishu_app_bot_card_notification(payload)

        self.assertEqual(result.status, "failed")
        self.assertIn("token down", result.message)

    def test_send_loads_project_env_when_process_env_is_missing(self) -> None:
        def load_env() -> bool:
            os.environ["FEISHU_WEBHOOK_URL"] = "https://example.invalid/webhook"
            return True

        with patch.dict(os.environ, {}, clear=True):
            with patch("services.feishu_service.load_project_environment", side_effect=load_env, create=True):
                with patch("services.feishu_service.urlopen") as mocked_urlopen:
                    mocked_urlopen.return_value.__enter__.return_value.status = 200
                    result = send_feishu_text_notification("test message")

        self.assertEqual(result.status, "success")


if __name__ == "__main__":
    unittest.main()
