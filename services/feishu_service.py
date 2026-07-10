import json
import os
from dataclasses import dataclass
from urllib.request import Request, urlopen

from models.business import Logistics, Order, Ticket


FEISHU_WEBHOOK_ENV = "FEISHU_WEBHOOK_URL"

##这里创建了之后就不允许再次更改了。
@dataclass(frozen=True)
class FeishuNotificationResult:
    status: str
    message: str


def build_feishu_ticket_message(
    *,
    ticket: Ticket,
    order: Order,
    logistics: Logistics,
) -> str:
    return "\n".join(
        [
            "【电商售后异常工单】",
            f"工单ID：{ticket.ticket_id}",
            f"订单号：{order.order_id}",
            f"用户ID：{order.user_id}",
            f"商品：{order.product_name}",
            f"优先级：{ticket.priority}",
            f"工单摘要：{ticket.summary}",
            f"物流状态：{logistics.carrier} / {logistics.tracking_no} / {logistics.status}",
            f"最新物流：{logistics.last_event}",
            f"建议动作：{ticket.suggested_action}",
        ]
    )


def send_feishu_text_notification(
    text: str,
    *,
    webhook_url: str | None = None,
    timeout_seconds: float = 3.0,
) -> FeishuNotificationResult:
    target_url = webhook_url if webhook_url is not None else os.getenv(FEISHU_WEBHOOK_ENV)
    if not target_url:
        return FeishuNotificationResult(
            status="disabled",
            message="FEISHU_WEBHOOK_URL is not configured",
        )

    payload = json.dumps(
        {
            "msg_type": "text",
            "content": {
                "text": text,
            },
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = Request(
        target_url,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status_code = response.status if hasattr(response, "status") else response.getcode()
            if status_code >= 400:
                return FeishuNotificationResult(
                    status="failed",
                    message=f"Feishu webhook returned HTTP {status_code}",
                )
    except Exception as exc:
        return FeishuNotificationResult(status="failed", message=str(exc))

    return FeishuNotificationResult(status="success", message="Feishu webhook sent")
