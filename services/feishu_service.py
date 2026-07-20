import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.request import Request, urlopen

from models.business import Logistics, Order, Ticket
from services.environment import load_project_environment


FEISHU_WEBHOOK_ENV = "FEISHU_WEBHOOK_URL"
FEISHU_APP_ID_ENV = "FEISHU_APP_ID"
FEISHU_APP_SECRET_ENV = "FEISHU_APP_SECRET"
FEISHU_CHAT_ID_ENV = "FEISHU_CHAT_ID"
FEISHU_TENANT_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
FEISHU_MESSAGE_URL = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"

##这里创建了之后就不允许再次更改了。
@dataclass(frozen=True)
class FeishuNotificationResult:
    status: str
    message: str


@dataclass(frozen=True)
class FeishuAppBotConfig:
    app_id: str
    app_secret: str
    chat_id: str


def format_message_time(value: datetime | None) -> str:
    return (value or datetime.utcnow()).strftime("%Y-%m-%d %H:%M:%S")


def get_feishu_app_bot_config() -> FeishuAppBotConfig | None:
    if not all(
        [
            os.getenv(FEISHU_APP_ID_ENV),
            os.getenv(FEISHU_APP_SECRET_ENV),
            os.getenv(FEISHU_CHAT_ID_ENV),
        ]
    ):
        load_project_environment()

    app_id = os.getenv(FEISHU_APP_ID_ENV)
    app_secret = os.getenv(FEISHU_APP_SECRET_ENV)
    chat_id = os.getenv(FEISHU_CHAT_ID_ENV)
    if not app_id or not app_secret or not chat_id:
        return None
    return FeishuAppBotConfig(app_id=app_id, app_secret=app_secret, chat_id=chat_id)


def fetch_feishu_tenant_access_token(
    config: FeishuAppBotConfig,
    *,
    timeout_seconds: float = 3.0,
) -> str:
    body = json.dumps(
        {
            "app_id": config.app_id,
            "app_secret": config.app_secret,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = Request(
        FEISHU_TENANT_TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        response_body = json.loads(response.read().decode("utf-8"))

    if response_body.get("code") != 0 or not response_body.get("tenant_access_token"):
        raise RuntimeError(f"Feishu tenant token failed: {response_body.get('msg') or response_body.get('code')}")
    return response_body["tenant_access_token"]


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


def build_feishu_approval_decision_card(
    *,
    ticket: Ticket,
    operator: str,
    action: str,
    decided_at: datetime | None = None,
) -> dict[str, Any]:
    decided_time = format_message_time(decided_at or ticket.approval_decided_at)
    if action == "approve":
        title = "售后处理已通过"
        template = "green"
        result_text = "审核通过"
    elif action == "reject":
        title = "售后处理已拒绝"
        template = "red"
        result_text = "审核拒绝"
    else:
        title = "售后处理已转人工确认"
        template = "blue"
        result_text = "转人工确认"

    return {
        "schema": "2.0",
        "config": {"wide_screen_mode": True},
        "header": {
            "template": template,
            "title": {"tag": "plain_text", "content": title},
        },
        "body": {
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**处理结果**：{result_text}\n"
                            f"**工单 ID**：{ticket.ticket_id}\n"
                            f"**订单 ID**：{ticket.order_id}\n"
                            f"**处理人**：{operator}\n"
                            f"**处理时间**：{decided_time}"
                        ),
                    },
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**工单状态**：{ticket.status}\n"
                            f"**审核状态**：{ticket.approval_status}\n"
                            f"**处理建议**：{ticket.suggested_action}"
                        ),
                    },
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


def send_feishu_app_bot_card_notification(
    payload: dict[str, Any],
    *,
    timeout_seconds: float = 3.0,
) -> FeishuNotificationResult:
    config = get_feishu_app_bot_config()
    if config is None:
        return FeishuNotificationResult(
            status="disabled",
            message="FEISHU_APP_ID, FEISHU_APP_SECRET, or FEISHU_CHAT_ID is not configured",
        )

    try:
        tenant_access_token = fetch_feishu_tenant_access_token(config, timeout_seconds=timeout_seconds)
        body = json.dumps(
            {
                "receive_id": config.chat_id,
                "msg_type": payload["msg_type"],
                "content": json.dumps(payload["card"], ensure_ascii=False),
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            FEISHU_MESSAGE_URL,
            data=body,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {tenant_access_token}",
            },
            method="POST",
        )
        with urlopen(request, timeout=timeout_seconds) as response:
            status_code = response.status if hasattr(response, "status") else response.getcode()
            response_body = json.loads(response.read().decode("utf-8") or "{}")
            if status_code >= 400 or response_body.get("code") != 0:
                return FeishuNotificationResult(
                    status="failed",
                    message=f"Feishu app bot returned {response_body.get('msg') or status_code}",
                )
    except Exception as exc:
        return FeishuNotificationResult(status="failed", message=str(exc))

    return FeishuNotificationResult(status="success", message="Feishu app bot card sent")


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
