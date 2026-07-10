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
    build_feishu_ticket_message,
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


if __name__ == "__main__":
    unittest.main()
