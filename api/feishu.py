import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.business import get_ticket_or_404
from models.feishu_event import FeishuEvent
from models.database import get_db
from schemas.business import (
    FeishuCallbackRequest,
    FeishuCallbackResponse,
    FeishuEventRead,
    TicketEventRead,
    TicketRead,
)
from services.ticket_transition_service import TicketTransitionError, apply_ticket_transition


router = APIRouter(prefix="/api/feishu", tags=["feishu"])


@router.post("/callback", response_model=FeishuCallbackResponse)
def handle_callback(
    payload: FeishuCallbackRequest,
    db: Session = Depends(get_db),
) -> dict:
    ticket = get_ticket_or_404(db, payload.ticket_id)
    try:
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
        payload=json.dumps(payload.model_dump(), ensure_ascii=False),
        created_at=ticket_event.created_at,
        processed_at=ticket_event.created_at,
    )
    db.add(feishu_event)
    db.commit()
    db.refresh(ticket_event)
    db.refresh(feishu_event)

    return {
        "ticket": get_ticket_or_404(db, ticket.ticket_id),
        "ticket_event": ticket_event,
        "feishu_event": feishu_event,
    }
