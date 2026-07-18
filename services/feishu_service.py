import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.request import Request, urlopen

from models.business import Logistics, Order, Ticket
from services.environment import load_project_environment


FEISHU_WEBHOOK_ENV = "FEISHU_WEBHOOK_URL"

##这里创建了之后就不允许再次更改了。
@dataclass(frozen=True)
class FeishuNotificationResult:
    status: str
    message: str


def format_message_time(value: datetime | None) -> str:
    return (value or datetime.utcnow()).strftime("%Y-%m-%d %H:%M:%S")


def build_feishu_ticket_message(
    *,
    ticket: Ticket,
    order: Order,
    logistics: Logistics,
) -> str:
    response_level = "高" if ticket.priority == "high" else "普通"
    return "\n".join(
        [
            "【电商售后异常工单】",
            f"响应等级：{response_level}",
            f"工单ID：{ticket.ticket_id}",
            f"订单ID：{order.order_id}",
            f"申请时间：{format_message_time(ticket.created_at)}",
            f"申请人：{ticket.created_by}",
            f"用户ID：{order.user_id}",
            f"商品：{order.product_name}",
            f"优先级：{ticket.priority}",
            f"工单摘要：{ticket.summary}",
            f"物流状态：{logistics.carrier} / {logistics.tracking_no} / {logistics.status}",
            f"最新物流：{logistics.last_event}",
            f"建议动作：{ticket.suggested_action}",
        ]
    )


def build_feishu_approval_message(
    *,
    order: Order,
    response_level: str,
    applicant: str,
    approval_reason: str,
    suggested_action: str,
    requested_at: datetime | None = None,
) -> str:
    request_time = requested_at or datetime.utcnow()
    return "\n".join(
        [
            "【售后处理待审核】",
            f"响应等级：{response_level}",
            f"订单ID：{order.order_id}",
            f"申请时间：{format_message_time(request_time)}",
            f"申请人：{applicant}",
            f"用户ID：{order.user_id}",
            f"商品：{order.product_name}",
            f"审核原因：{approval_reason}",
            f"建议动作：{suggested_action}",
        ]
    )


def build_feishu_approval_card_payload(
    *,
    ticket: Ticket,
    order: Order,
    applicant: str,
    approval_reason: str | None,
    suggested_action: str,
    requested_at: datetime | None = None,
) -> dict[str, Any]:
    response_level = "高" if ticket.priority == "high" else "普通"
    request_time = format_message_time(requested_at or ticket.created_at)
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "orange",
                "title": {"tag": "plain_text", "content": "售后处理待审核"},
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**响应等级**：{response_level}\n"
                            f"**工单 ID**：{ticket.ticket_id}\n"
                            f"**订单 ID**：{order.order_id}\n"
                            f"**申请时间**：{request_time}\n"
                            f"**申请人**：{applicant}\n"
                            f"**用户 ID**：{order.user_id}"
                        ),
                    },
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**审核原因**：{approval_reason or '涉及高风险售后动作，需要人工审核'}\n"
                            f"**建议动作**：{suggested_action}"
                        ),
                    },
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "通过"},
                            "type": "primary",
                            "value": {"ticket_id": ticket.ticket_id, "action": "approve"},
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "拒绝"},
                            "type": "danger",
                            "value": {"ticket_id": ticket.ticket_id, "action": "reject"},
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "转人工确认"},
                            "value": {"ticket_id": ticket.ticket_id, "action": "manual_confirm"},
                        },
                    ],
                },
            ],
        },
    }


def send_feishu_payload(
    payload: dict[str, Any],
    *,
    webhook_url: str | None = None,
    timeout_seconds: float = 3.0,
) -> FeishuNotificationResult:
    if webhook_url is None and not os.getenv(FEISHU_WEBHOOK_ENV):
        load_project_environment()
    target_url = webhook_url if webhook_url is not None else os.getenv(FEISHU_WEBHOOK_ENV)
    if not target_url:
        return FeishuNotificationResult(
            status="disabled",
            message="FEISHU_WEBHOOK_URL is not configured",
        )

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        target_url,
        data=body,
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


def send_feishu_card_notification(
    payload: dict[str, Any],
    *,
    webhook_url: str | None = None,
    timeout_seconds: float = 3.0,
) -> FeishuNotificationResult:
    return send_feishu_payload(payload, webhook_url=webhook_url, timeout_seconds=timeout_seconds)


def send_feishu_text_notification(
    text: str,
    *,
    webhook_url: str | None = None,
    timeout_seconds: float = 3.0,
) -> FeishuNotificationResult:
    payload = {
        "msg_type": "text",
        "content": {
            "text": text,
        },
    }
    return send_feishu_payload(
        payload,
        webhook_url=webhook_url,
        timeout_seconds=timeout_seconds,
    )
