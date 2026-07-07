from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from models.business import Logistics, Order, Ticket, TicketEvent, utc_now
from models.database import get_db
from schemas.business import (
    LogisticsRead,
    OrderRead,
    TicketCreate,
    TicketEventCreate,
    TicketEventRead,
    TicketRead,
    TicketUpdate,
)


router = APIRouter(prefix="/api", tags=["business"])


def make_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8].upper()}"


def get_ticket_or_404(db: Session, ticket_id: str) -> Ticket:
    ticket = db.scalar(
        select(Ticket)
        .options(selectinload(Ticket.events))
        .where(Ticket.ticket_id == ticket_id)
    )
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


@router.get("/orders/{order_id}", response_model=OrderRead)
def get_order(order_id: str, db: Session = Depends(get_db)) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


@router.get("/logistics/{order_id}", response_model=LogisticsRead)
def get_logistics(order_id: str, db: Session = Depends(get_db)) -> Logistics:
    logistics = db.scalar(select(Logistics).where(Logistics.order_id == order_id))
    if logistics is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Logistics not found")
    return logistics


@router.post("/tickets", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)) -> Ticket:
    if db.get(Order, payload.order_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    ticket = Ticket(
        ticket_id=make_id("TCK"),
        ticket_type=payload.ticket_type,
        priority=payload.priority,
        status="todo",
        user_id=payload.user_id,
        order_id=payload.order_id,
        summary=payload.summary,
        suggested_action=payload.suggested_action,
        assigned_to=payload.assigned_to,
        created_by=payload.created_by,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return get_ticket_or_404(db, ticket.ticket_id)


@router.get("/tickets", response_model=list[TicketRead])
def list_tickets(db: Session = Depends(get_db)) -> list[Ticket]:
    return list(
        db.scalars(
            select(Ticket)
            .options(selectinload(Ticket.events))
            .order_by(Ticket.created_at.desc())
        )
    )


@router.get("/tickets/{ticket_id}", response_model=TicketRead)
def get_ticket(ticket_id: str, db: Session = Depends(get_db)) -> Ticket:
    return get_ticket_or_404(db, ticket_id)


@router.patch("/tickets/{ticket_id}", response_model=TicketRead)
def update_ticket(ticket_id: str, payload: TicketUpdate, db: Session = Depends(get_db)) -> Ticket:
    ticket = get_ticket_or_404(db, ticket_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(ticket, field, value)
    ticket.updated_at = utc_now()
    db.commit()
    db.refresh(ticket)
    return get_ticket_or_404(db, ticket.ticket_id)


@router.post(
    "/tickets/{ticket_id}/events",
    response_model=TicketEventRead,
    status_code=status.HTTP_201_CREATED,
)
def create_ticket_event(
    ticket_id: str,
    payload: TicketEventCreate,
    db: Session = Depends(get_db),
) -> TicketEvent:
    ticket = get_ticket_or_404(db, ticket_id)
    event = TicketEvent(
        event_id=make_id("EVT"),
        ticket_id=ticket.ticket_id,
        event_type=payload.event_type,
        operator=payload.operator,
        content=payload.content,
        from_status=payload.from_status,
        to_status=payload.to_status,
    )
    db.add(event)
    ticket.updated_at = utc_now()
    db.commit()
    db.refresh(event)
    return event
