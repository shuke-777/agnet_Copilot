import json
from typing import Any

from pydantic import ValidationError
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.business import get_ticket_or_404
from models.business import TicketEvent
from models.feishu_event import FeishuEvent
from models.database import get_db
from schemas.business import (
    FeishuCallbackRequest,
    FeishuCallbackResponse,
    FeishuEventRead,
    TicketEventRead,
    TicketRead,
)
from services.ticket_transition_service import (
    TicketTransitionError,
    apply_ticket_approval,
    apply_ticket_transition,
)
from services.feishu_service import build_feishu_approval_decision_card
from services.dashboard_cache_service import invalidate_dashboard_cache
from services.risk_ranking_service import refresh_risk_rankings
from services.operation_log_service import record_operation_log


router = APIRouter(prefix="/api/feishu", tags=["feishu"])


APPROVAL_ACTIONS = {"approve", "reject", "manual_confirm"}
APPROVAL_ACTION_TARGETS = {
    "approve": "approved",
    "reject": "rejected",
    "manual_confirm": "pending",
}


def parse_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def first_present(*values: Any) -> str | None:
    for value in values:
        if value is not None and str(value).strip():
            return str(value)
    return None


def extract_feishu_operator(event: dict[str, Any]) -> str:
    operator = parse_json_object(event.get("operator"))
    return first_present(
        operator.get("name"),
        operator.get("user_name"),
        operator.get("open_id"),
        operator.get("user_id"),
        operator.get("union_id"),
        event.get("operator_name"),
    ) or "飞书用户"


def normalize_feishu_callback_payload(payload: dict[str, Any]) -> FeishuCallbackRequest:
    if {"event_id", "ticket_id", "action", "operator"}.issubset(payload.keys()):
        return FeishuCallbackRequest.model_validate(payload)

    header = parse_json_object(payload.get("header"))
    event = parse_json_object(payload.get("event"))
    action = parse_json_object(event.get("action") or payload.get("action"))
    action_value = parse_json_object(action.get("value"))

    normalized = {
        "event_id": first_present(
            header.get("event_id"),
            event.get("event_id"),
            payload.get("uuid"),
            payload.get("event_id"),
            action_value.get("event_id"),
        ),
        "ticket_id": action_value.get("ticket_id"),
        "action": action_value.get("action"),
        "operator": extract_feishu_operator(event),
    }
    return FeishuCallbackRequest.model_validate(normalized)


def is_real_feishu_card_action_payload(payload: dict[str, Any]) -> bool:
    header = parse_json_object(payload.get("header"))
    event = parse_json_object(payload.get("event"))
    return first_present(
        header.get("event_type"),
        event.get("type"),
        payload.get("type"),
    ) == "card.action.trigger"


def build_callback_response(
    *,
    ticket,
    ticket_event: TicketEvent,
    feishu_event: FeishuEvent,
) -> dict:
    return FeishuCallbackResponse(
        ticket=TicketRead.model_validate(ticket),
        ticket_event=TicketEventRead.model_validate(ticket_event),
        feishu_event=FeishuEventRead.model_validate(feishu_event),
    ).model_dump(mode="json")


def build_real_card_callback_response(
    *,
    ticket,
    ticket_event: TicketEvent,
    feishu_event: FeishuEvent,
) -> dict:
    card = build_feishu_approval_decision_card(
        ticket=ticket,
        operator=feishu_event.operator,
        action=feishu_event.action,
        decided_at=ticket_event.created_at,
    )
    return {
        "toast": {
            "type": "success",
            "content": ticket_event.content,
        },
        "card": {
            "type": "raw",
            "data": card,
        },
    }


def get_existing_approval_event(
    db: Session,
    *,
    ticket_id: str,
    action: str,
) -> FeishuEvent | None:
    return db.scalar(
        select(FeishuEvent)
        .where(
            FeishuEvent.ticket_id == ticket_id,
            FeishuEvent.action == action,
            FeishuEvent.status.in_(("processed", "duplicate")),
        )
        .order_by(FeishuEvent.processed_at.desc())
    )


def get_ticket_event_for_feishu_event(
    db: Session,
    feishu_event: FeishuEvent,
) -> TicketEvent | None:
    return db.scalar(
        select(TicketEvent)
        .where(
            TicketEvent.ticket_id == feishu_event.ticket_id,
            TicketEvent.event_type.in_(("feishu_status_changed", "feishu_approval_changed")),
            TicketEvent.operator == feishu_event.operator,
            TicketEvent.from_status == feishu_event.from_status,
            TicketEvent.to_status == feishu_event.to_status,
            TicketEvent.created_at == feishu_event.processed_at,
        )
        .order_by(TicketEvent.created_at.desc())
    )


def approval_action_already_applied(*, ticket, action: str) -> bool:
    expected_approval_status = APPROVAL_ACTION_TARGETS.get(action)
    if expected_approval_status is None:
        return False
    if action == "manual_confirm":
        return ticket.approval_status == "pending" and ticket.status == "processing"
    return ticket.approval_status == expected_approval_status


@router.post("/callback", response_model=None)
def handle_callback(
    payload: dict,
    db: Session = Depends(get_db),
) -> dict:
    if payload.get("challenge"):
        return {"challenge": payload["challenge"]}

    raw_payload = payload
    try:
        callback_payload = normalize_feishu_callback_payload(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc

    payload = callback_payload
    is_real_card_action = is_real_feishu_card_action_payload(raw_payload)
    existing_event = db.get(FeishuEvent, payload.event_id)
    if existing_event is not None:
        if (
            existing_event.ticket_id != payload.ticket_id
            or existing_event.action != payload.action
            or existing_event.operator != payload.operator
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Feishu event id conflicts with an existing callback",
            )

        ticket = get_ticket_or_404(db, existing_event.ticket_id)
        ticket_event = get_ticket_event_for_feishu_event(db, existing_event)
        if ticket_event is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Existing Feishu callback is missing its ticket event",
            )
        if is_real_card_action and existing_event.action in APPROVAL_ACTIONS:
            return build_real_card_callback_response(
                ticket=ticket,
                ticket_event=ticket_event,
                feishu_event=existing_event,
            )
        return build_callback_response(
            ticket=ticket,
            ticket_event=ticket_event,
            feishu_event=existing_event,
        )

    ticket = get_ticket_or_404(db, payload.ticket_id)
    if (
        is_real_card_action
        and payload.action in APPROVAL_ACTIONS
        and approval_action_already_applied(ticket=ticket, action=payload.action)
    ):
        existing_approval_event = get_existing_approval_event(
            db,
            ticket_id=ticket.ticket_id,
            action=payload.action,
        )
        if existing_approval_event is not None:
            ticket_event = get_ticket_event_for_feishu_event(db, existing_approval_event)
            if ticket_event is not None:
                duplicate_event = FeishuEvent(
                    event_id=payload.event_id,
                    ticket_id=ticket.ticket_id,
                    action=payload.action,
                    operator=payload.operator,
                    from_status=existing_approval_event.from_status,
                    to_status=existing_approval_event.to_status,
                    status="duplicate",
                    payload=json.dumps(raw_payload, ensure_ascii=False),
                    created_at=ticket_event.created_at,
                    processed_at=ticket_event.created_at,
                )
                db.add(duplicate_event)
                record_operation_log(
                    db,
                    operator=payload.operator,
                    operator_type="feishu",
                    action="feishu_callback_duplicate",
                    target_type="feishu_event",
                    target_id=duplicate_event.event_id,
                    ticket_id=ticket.ticket_id,
                    order_id=ticket.order_id,
                    source="feishu",
                    status="duplicate",
                    summary=f"飞书重复回调 {payload.action}，复用已处理结果。",
                    extra_data={"event_id": payload.event_id, "action": payload.action},
                )
                db.commit()
                db.refresh(duplicate_event)
                return build_real_card_callback_response(
                    ticket=ticket,
                    ticket_event=ticket_event,
                    feishu_event=duplicate_event,
                )

    try:
        if payload.action in APPROVAL_ACTIONS:
            ticket_event = apply_ticket_approval(
                db,
                ticket=ticket,
                action=payload.action,
                operator=payload.operator,
                event_type="feishu_approval_changed",
                content_prefix="飞书审核操作",
            )
        else:
            ticket_event = apply_ticket_transition(
                db,
                ticket=ticket,
                action=payload.action,
                operator=payload.operator,
                event_type="feishu_status_changed",
                content_prefix="飞书按钮操作",
            )
    except TicketTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    feishu_event = FeishuEvent(
        event_id=payload.event_id,
        ticket_id=ticket.ticket_id,
        action=payload.action,
        operator=payload.operator,
        from_status=ticket_event.from_status,
        to_status=ticket_event.to_status,
        status="processed",
        payload=json.dumps(raw_payload, ensure_ascii=False),
        created_at=ticket_event.created_at,
        processed_at=ticket_event.created_at,
    )
    db.add(feishu_event)
    record_operation_log(
        db,
        operator=payload.operator,
        operator_type="feishu",
        action="feishu_callback_received",
        target_type="feishu_event",
        target_id=feishu_event.event_id,
        ticket_id=ticket.ticket_id,
        order_id=ticket.order_id,
        source="feishu",
        status="success",
        summary=f"接收飞书回调并执行 {payload.action}。",
        extra_data={"event_id": payload.event_id, "action": payload.action},
    )
    record_operation_log(
        db,
        operator=payload.operator,
        operator_type="feishu",
        action="approval_changed" if payload.action in APPROVAL_ACTIONS else "feishu_status_changed",
        target_type="ticket",
        target_id=ticket.ticket_id,
        ticket_id=ticket.ticket_id,
        order_id=ticket.order_id,
        source="feishu",
        status="success",
        summary=ticket_event.content,
        before_data={"status": ticket_event.from_status},
        after_data={"status": ticket_event.to_status},
    )
    db.commit()
    db.refresh(ticket_event)
    db.refresh(feishu_event)
    invalidate_dashboard_cache()
    refresh_risk_rankings(db)

    refreshed_ticket = get_ticket_or_404(db, ticket.ticket_id)
    if is_real_card_action and feishu_event.action in APPROVAL_ACTIONS:
        return build_real_card_callback_response(
            ticket=refreshed_ticket,
            ticket_event=ticket_event,
            feishu_event=feishu_event,
        )

    return build_callback_response(
        ticket=refreshed_ticket,
        ticket_event=ticket_event,
        feishu_event=feishu_event,
    )
