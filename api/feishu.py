import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.business import get_ticket_or_404, make_id
from models.business import TicketEvent, utc_now
from models.feishu_event import FeishuEvent
from models.database import get_db
from schemas.business import (
    FeishuCallbackRequest,
    FeishuCallbackResponse,
    FeishuEventRead,
    TicketEventRead,
    TicketRead,
)


router = APIRouter(prefix="/api/feishu", tags=["feishu"])


STATUS_TRANSITIONS = {
    "claim": ("todo", "processing"),
    "resolve": ("processing", "resolved"),
    "reopen": ("resolved", "processing"),
}


@router.post("/callback", response_model=FeishuCallbackResponse)
def handle_callback(
    payload: FeishuCallbackRequest,
    db: Session = Depends(get_db),
) -> dict:
    ticket = get_ticket_or_404(db, payload.ticket_id)
    expected_from, to_status = STATUS_TRANSITIONS[payload.action]
    if ticket.status != expected_from:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"cannot transition ticket {ticket.ticket_id} from "
                f"{ticket.status} with action {payload.action}"
            ),
        )

    now = utc_now()
    ticket_event = TicketEvent(
        event_id=make_id("EVT"),
        ticket_id=ticket.ticket_id,
        event_type="feishu_status_changed",
        operator=payload.operator,
        content=f"飞书按钮操作：{payload.operator} 执行 {payload.action}",
        from_status=ticket.status,
        to_status=to_status,
        created_at=now,
    )
    feishu_event = FeishuEvent(
        event_id=payload.event_id,
        ticket_id=ticket.ticket_id,
        action=payload.action,
        operator=payload.operator,
        from_status=ticket.status,
        to_status=to_status,
        status="processed",
        payload=json.dumps(payload.model_dump(), ensure_ascii=False),
        created_at=now,
        processed_at=now,
    )
    ticket.status = to_status
    if payload.action in {"claim", "reopen"}:
        ticket.assigned_to = payload.operator
    ticket.updated_at = now
    db.add_all([ticket_event, feishu_event])
    db.commit()
    db.refresh(ticket_event)
    db.refresh(feishu_event)

    return {
        "ticket": get_ticket_or_404(db, ticket.ticket_id),
        "ticket_event": ticket_event,
        "feishu_event": feishu_event,
    }
