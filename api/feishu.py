import json

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
from services.dashboard_cache_service import invalidate_dashboard_cache
from services.risk_ranking_service import refresh_risk_rankings


router = APIRouter(prefix="/api/feishu", tags=["feishu"])


APPROVAL_ACTIONS = {"approve", "reject", "manual_confirm"}


@router.post("/callback", response_model=FeishuCallbackResponse)
def handle_callback(
    payload: FeishuCallbackRequest,
    db: Session = Depends(get_db),
) -> dict:
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
        ticket_event = db.scalar(
            select(TicketEvent)
            .where(
                TicketEvent.ticket_id == existing_event.ticket_id,
                TicketEvent.event_type.in_(("feishu_status_changed", "feishu_approval_changed")),
                TicketEvent.operator == existing_event.operator,
                TicketEvent.from_status == existing_event.from_status,
                TicketEvent.to_status == existing_event.to_status,
                TicketEvent.created_at == existing_event.processed_at,
            )
            .order_by(TicketEvent.created_at.desc())
        )
        if ticket_event is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Existing Feishu callback is missing its ticket event",
            )
        return {
            "ticket": ticket,
            "ticket_event": ticket_event,
            "feishu_event": existing_event,
        }

    ticket = get_ticket_or_404(db, payload.ticket_id)
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
        payload=json.dumps(payload.model_dump(), ensure_ascii=False),
        created_at=ticket_event.created_at,
        processed_at=ticket_event.created_at,
    )
    db.add(feishu_event)
    db.commit()
    db.refresh(ticket_event)
    db.refresh(feishu_event)
    invalidate_dashboard_cache()
    refresh_risk_rankings(db)

    return {
        "ticket": get_ticket_or_404(db, ticket.ticket_id),
        "ticket_event": ticket_event,
        "feishu_event": feishu_event,
    }
