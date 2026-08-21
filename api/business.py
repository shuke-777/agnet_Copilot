from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from models.business import Logistics, Order, Ticket, TicketEvent, utc_now
from models.agent_trace import AgentRun
from models.operation_log import OperationLog
from models.database import get_db
from schemas.business import (
    LogisticsRead,
    OrderRead,
    TicketCreate,
    TicketActionRequest,
    TicketEventCreate,
    TicketEventRead,
    TicketRead,
    TicketUpdate,
    Customer360Read,
    Customer360TimelineItem,
)
from services.ticket_transition_service import TicketTransitionError, apply_ticket_transition
from services.dashboard_cache_service import invalidate_dashboard_cache
from services.risk_ranking_service import refresh_risk_rankings
from services.operation_log_service import record_operation_log
from services.sla_service import mark_sla_overdue


router = APIRouter(prefix="/api", tags=["business"])


def make_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8].upper()}"


def get_ticket_or_404(db: Session, ticket_id: str) -> Ticket:
    ticket = db.scalar(
        select(Ticket)
        .options(
            selectinload(Ticket.events),
            selectinload(Ticket.source_run),
            selectinload(Ticket.related_runs),
        )
        .where(Ticket.ticket_id == ticket_id)
    )
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    if mark_sla_overdue(db, ticket):
        db.commit()
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
        approval_required=payload.approval_required,
        approval_status=payload.approval_status,
        approval_reason=payload.approval_reason,
    )
    db.add(ticket)
    record_operation_log(
        db,
        operator=payload.created_by,
        operator_type="agent" if payload.created_by == "agent" else "human",
        action="ticket_created",
        target_type="ticket",
        target_id=ticket.ticket_id,
        ticket_id=ticket.ticket_id,
        order_id=ticket.order_id,
        source="business_api",
        status="success",
        summary=f"创建工单 {ticket.ticket_id}。",
        after_data={"status": ticket.status, "priority": ticket.priority},
    )
    db.commit()
    db.refresh(ticket)
    invalidate_dashboard_cache()
    refresh_risk_rankings(db)
    return get_ticket_or_404(db, ticket.ticket_id)


@router.get("/tickets", response_model=list[TicketRead])
def list_tickets(q: str | None = None, db: Session = Depends(get_db)) -> list[Ticket]:
    statement = select(Ticket).options(
        selectinload(Ticket.events),
        selectinload(Ticket.source_run),
        selectinload(Ticket.related_runs),
    )
    if q and q.strip():
        query = q.strip().upper()
        statement = statement.where(
            or_(
                Ticket.ticket_id.ilike(f"%{query}%"),
                Ticket.source_run_id.ilike(f"%{query}%"),
                Ticket.order_id.ilike(f"%{query}%"),
            )
        )
    tickets = list(db.scalars(statement.order_by(Ticket.created_at.desc())))
    if any(mark_sla_overdue(db, ticket) for ticket in tickets):
        db.commit()
    return tickets


@router.get("/todos", response_model=list[TicketRead])
def list_todos(
    status: str | None = None,
    priority: str | None = None,
    assigned_to: str | None = None,
    overdue: bool | None = None,
    db: Session = Depends(get_db),
) -> list[Ticket]:
    statement = select(Ticket).options(
        selectinload(Ticket.events),
        selectinload(Ticket.source_run),
        selectinload(Ticket.related_runs),
    )
    if status:
        statement = statement.where(Ticket.status == status)
    if priority:
        statement = statement.where(Ticket.priority == priority)
    if assigned_to:
        statement = statement.where(Ticket.assigned_to == assigned_to)
    tickets = list(db.scalars(statement.order_by(Ticket.created_at.asc())))
    changed = any(mark_sla_overdue(db, ticket) for ticket in tickets)
    if changed:
        db.commit()
    if overdue is not None:
        tickets = [ticket for ticket in tickets if ticket.sla_overdue is overdue]
    return tickets


@router.get("/tickets/{ticket_id}", response_model=TicketRead)
def get_ticket(ticket_id: str, db: Session = Depends(get_db)) -> Ticket:
    return get_ticket_or_404(db, ticket_id)


@router.patch("/tickets/{ticket_id}", response_model=TicketRead)
def update_ticket(ticket_id: str, payload: TicketUpdate, db: Session = Depends(get_db)) -> Ticket:
    ticket = get_ticket_or_404(db, ticket_id)
    updates = payload.model_dump(exclude_unset=True)
    before_data = {field: getattr(ticket, field) for field in updates}
    for field, value in updates.items():
        setattr(ticket, field, value)
    ticket.updated_at = utc_now()
    record_operation_log(
        db,
        operator="客服后台",
        operator_type="human",
        action="ticket_updated",
        target_type="ticket",
        target_id=ticket.ticket_id,
        ticket_id=ticket.ticket_id,
        order_id=ticket.order_id,
        source="business_api",
        status="success",
        summary=f"更新工单 {ticket.ticket_id}。",
        before_data=before_data,
        after_data=updates,
    )
    db.commit()
    db.refresh(ticket)
    invalidate_dashboard_cache()
    refresh_risk_rankings(db)
    return get_ticket_or_404(db, ticket.ticket_id)


@router.post("/tickets/{ticket_id}/actions", response_model=TicketRead)
def apply_ticket_action(
    ticket_id: str,
    payload: TicketActionRequest,
    db: Session = Depends(get_db),
) -> Ticket:
    ticket = get_ticket_or_404(db, ticket_id)
    before_data = {"status": ticket.status, "assigned_to": ticket.assigned_to}
    try:
        apply_ticket_transition(
            db,
            ticket=ticket,
            action=payload.action,
            operator=payload.operator,
            event_type="manual_status_changed",
            content_prefix="后台人工操作",
        )
    except TicketTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    record_operation_log(
        db,
        operator=payload.operator,
        operator_type="human",
        action="manual_status_changed",
        target_type="ticket",
        target_id=ticket.ticket_id,
        ticket_id=ticket.ticket_id,
        order_id=ticket.order_id,
        source="admin",
        status="success",
        summary=f"{payload.operator} 对工单执行 {payload.action}。",
        before_data=before_data,
        after_data={"status": ticket.status, "assigned_to": ticket.assigned_to},
    )
    db.commit()
    invalidate_dashboard_cache()
    refresh_risk_rankings(db)
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
    record_operation_log(
        db,
        operator=payload.operator,
        operator_type="human",
        action="ticket_event_created",
        target_type="ticket_event",
        target_id=event.event_id,
        ticket_id=ticket.ticket_id,
        order_id=ticket.order_id,
        source="business_api",
        status="success",
        summary=f"为工单 {ticket.ticket_id} 新增事件 {payload.event_type}。",
        after_data={"event_type": payload.event_type, "to_status": payload.to_status},
    )
    db.commit()
    db.refresh(event)
    invalidate_dashboard_cache()
    refresh_risk_rankings(db)
    return event


@router.get("/customers/{user_id}/360", response_model=Customer360Read)
def get_customer_360(
    user_id: str,
    order_id: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    order_statement = select(Order).where(Order.user_id == user_id)
    if order_id:
        order_statement = order_statement.where(Order.order_id == order_id.strip().upper())
    orders = list(db.scalars(order_statement.order_by(Order.created_at.desc())))
    order_ids = [order.order_id for order in orders]
    logistics = list(db.scalars(select(Logistics).where(Logistics.order_id.in_(order_ids)))) if order_ids else []
    ticket_statement = select(Ticket).options(
        selectinload(Ticket.events), selectinload(Ticket.source_run), selectinload(Ticket.related_runs)
    ).where(Ticket.user_id == user_id)
    if order_id:
        ticket_statement = ticket_statement.where(Ticket.order_id.in_(order_ids or [""]))
    tickets = list(db.scalars(ticket_statement.order_by(Ticket.created_at.desc())))
    if any(mark_sla_overdue(db, ticket) for ticket in tickets):
        db.commit()
    ticket_ids = [ticket.ticket_id for ticket in tickets]
    run_statement = select(AgentRun).where(AgentRun.user_id == user_id)
    if order_ids:
        run_statement = run_statement.where(or_(AgentRun.order_id.in_(order_ids), AgentRun.ticket_id.in_(ticket_ids or [""])))
    elif order_id:
        run_statement = run_statement.where(AgentRun.order_id == "")
    runs = list(db.scalars(run_statement.order_by(AgentRun.created_at.desc())))
    operation_statement = select(OperationLog).where(
        or_(OperationLog.order_id.in_(order_ids or [""]), OperationLog.ticket_id.in_(ticket_ids or [""]))
    )
    logs = list(db.scalars(operation_statement.order_by(OperationLog.created_at.desc()).limit(100)))
    timeline: list[dict] = []
    for order in orders:
        timeline.append({
            "timestamp": order.created_at,
            "kind": "order",
            "title": f"订单 {order.order_id} 创建",
            "detail": f"{order.product_name}，订单状态：{order.status}",
            "target_id": order.order_id,
            "order_id": order.order_id,
            "status": order.status,
        })
    for ticket in tickets:
        timeline.append({
            "timestamp": ticket.created_at,
            "kind": "ticket",
            "title": f"创建工单 {ticket.ticket_id}",
            "detail": ticket.summary,
            "target_id": ticket.ticket_id,
            "order_id": ticket.order_id,
            "ticket_id": ticket.ticket_id,
            "status": ticket.status,
        })
        for event in ticket.events:
            timeline.append({
                "timestamp": event.created_at,
                "kind": "ticket_event",
                "title": f"工单事件：{event.event_type}",
                "detail": event.content,
                "target_id": event.event_id,
                "order_id": ticket.order_id,
                "ticket_id": ticket.ticket_id,
                "status": event.to_status,
            })
    for run in runs:
        timeline.append({
            "timestamp": run.created_at,
            "kind": "agent_run",
            "title": f"Agent Run {run.run_id}",
            "detail": run.user_message,
            "target_id": run.run_id,
            "order_id": run.order_id,
            "ticket_id": run.ticket_id,
            "status": run.status,
        })
    for log in logs:
        timeline.append({
            "timestamp": log.created_at,
            "kind": "operation_log",
            "title": log.action,
            "detail": log.summary,
            "target_id": log.log_id,
            "order_id": log.order_id,
            "ticket_id": log.ticket_id,
            "status": log.status,
        })
    timeline.sort(key=lambda item: item["timestamp"], reverse=True)
    return {
        "user_id": user_id,
        "orders": orders,
        "logistics": logistics,
        "tickets": tickets,
        "related_runs": runs,
        "operation_logs": [
            {
                "log_id": log.log_id, "operator": log.operator, "action": log.action,
                "target_type": log.target_type, "target_id": log.target_id,
                "ticket_id": log.ticket_id, "run_id": log.run_id, "order_id": log.order_id,
                "source": log.source, "status": log.status, "summary": log.summary,
                "created_at": log.created_at,
            }
            for log in logs
        ],
        "timeline": timeline,
    }
