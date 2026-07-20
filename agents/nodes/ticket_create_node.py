from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.state import CopilotState
from api.business import make_id
from models.agent_trace import AgentRun
from models.business import Ticket, TicketEvent, utc_now
from services.session_ticket_binding_service import SessionTicketBindingService
from services.trace_service import record_agent_step
from services.operation_log_service import record_operation_log


def ticket_create_node(db: Session, state: CopilotState) -> CopilotState:
    if state.approval_required and state.approval_status == "pending":
        return _create_or_reuse_approval_ticket(db, state)

    if state.active_session_ticket is not None and state.intent in (
        "logistics_delay",
        "logistics_query",
        "shipping_timeliness",
    ):
        ticket = state.active_session_ticket
        state.ticket_association = "session_linked"
        output_summary = f"session_linked:{ticket.ticket_id}"
        return _associate_ticket(db, state, ticket, output_summary)

    if state.intent != "logistics_delay":
        return state

    if (
        state.order is None
        or state.order.status != "shipped"
        or not state.is_abnormal
        or not state.follow_up_requested
    ):
        return state

    ticket = db.scalar(
        select(Ticket)
        .where(
            Ticket.order_id == state.order.order_id,
            Ticket.ticket_type == "logistics_delay",
            Ticket.status.in_(("todo", "processing")),
        )
        .order_by(Ticket.created_at.asc())
    )
    if ticket is None:
        ticket = Ticket(
            ticket_id=make_id("TCK"),
            ticket_type="logistics_delay",
            priority="high",
            status="todo",
            user_id=state.order.user_id,
            order_id=state.order.order_id,
            source_run_id=state.run_id,
            summary=f"用户反馈订单 {state.order.order_id} 未收到，物流疑似异常。",
            suggested_action="联系承运商核实物流卡点，并同步用户预计处理时效。",
            assigned_to=None,
            created_by="agent",
        )
        db.add(ticket)
        db.flush()
        record_operation_log(
            db,
            operator="agent",
            operator_type="agent",
            action="ticket_created",
            target_type="ticket",
            target_id=ticket.ticket_id,
            ticket_id=ticket.ticket_id,
            run_id=state.run_id,
            order_id=ticket.order_id,
            source="copilot",
            status="success",
            summary="Copilot 创建物流异常工单。",
        )
        state.ticket_created = True
        state.ticket_association = "created"
        output_summary = f"created:{ticket.ticket_id}"
    else:
        now = utc_now()
        db.add(
            TicketEvent(
                event_id=make_id("EVT"),
                ticket_id=ticket.ticket_id,
                event_type="copilot_followup_analyzed",
                operator="agent",
                content=(
                    f"Copilot 追加分析：run_id={state.run_id}；"
                    f"用户问题={state.payload.user_message}；"
                    f"建议={state.reply_draft or '已生成售后处理建议'}"
                ),
                from_status=ticket.status,
                to_status=ticket.status,
                created_at=now,
            )
        )
        ticket.updated_at = now
        record_operation_log(
            db,
            operator="agent",
            operator_type="agent",
            action="ticket_reused",
            target_type="ticket",
            target_id=ticket.ticket_id,
            ticket_id=ticket.ticket_id,
            run_id=state.run_id,
            order_id=ticket.order_id,
            source="copilot",
            status="success",
            summary="Copilot 复用物流异常工单。",
        )
        state.ticket_reused = True
        state.ticket_association = "reused"
        output_summary = f"reused:{ticket.ticket_id}"

    SessionTicketBindingService(db).bind_ticket(
        session_id=state.payload.session_id,
        user_id=state.payload.user_id,
        order_id=ticket.order_id,
        ticket_id=ticket.ticket_id,
    )
    return _associate_ticket(db, state, ticket, output_summary)


def _create_or_reuse_approval_ticket(db: Session, state: CopilotState) -> CopilotState:
    if state.order is None:
        return state

    ticket_type = f"{state.intent or 'after_sales'}_approval"
    priority = "high" if state.order.amount >= 500 else "medium"
    ticket = db.scalar(
        select(Ticket)
        .where(
            Ticket.order_id == state.order.order_id,
            Ticket.ticket_type == ticket_type,
            Ticket.approval_status == "pending",
            Ticket.status.in_(("todo", "processing")),
        )
        .order_by(Ticket.created_at.asc())
    )
    if ticket is None:
        ticket = Ticket(
            ticket_id=make_id("TCK"),
            ticket_type=ticket_type,
            priority=priority,
            status="todo",
            user_id=state.order.user_id,
            order_id=state.order.order_id,
            source_run_id=state.run_id,
            summary=f"用户针对订单 {state.order.order_id} 提出{state.intent or '售后'}诉求，需要人工审核。",
            suggested_action=state.reply_draft or "请人工审核本次售后处理建议。",
            assigned_to=None,
            created_by="agent",
            approval_required=True,
            approval_status=state.approval_status,
            approval_reason=state.approval_reason,
        )
        db.add(ticket)
        db.flush()
        record_operation_log(
            db,
            operator="agent",
            operator_type="agent",
            action="ticket_created",
            target_type="ticket",
            target_id=ticket.ticket_id,
            ticket_id=ticket.ticket_id,
            run_id=state.run_id,
            order_id=ticket.order_id,
            source="copilot",
            status="success",
            summary="Copilot 创建待审核售后工单。",
        )
        state.ticket_created = True
        state.ticket_association = "created"
        output_summary = f"approval_created:{ticket.ticket_id}"
    else:
        now = utc_now()
        db.add(
            TicketEvent(
                event_id=make_id("EVT"),
                ticket_id=ticket.ticket_id,
                event_type="copilot_approval_followup_analyzed",
                operator="agent",
                content=(
                    f"Copilot 追加审核分析：run_id={state.run_id}；"
                    f"用户问题={state.payload.user_message}；"
                    f"建议={state.reply_draft or '已生成售后审核建议'}"
                ),
                from_status=ticket.approval_status,
                to_status=ticket.approval_status,
                created_at=now,
            )
        )
        ticket.updated_at = now
        record_operation_log(
            db,
            operator="agent",
            operator_type="agent",
            action="ticket_reused",
            target_type="ticket",
            target_id=ticket.ticket_id,
            ticket_id=ticket.ticket_id,
            run_id=state.run_id,
            order_id=ticket.order_id,
            source="copilot",
            status="success",
            summary="Copilot 复用待审核售后工单。",
        )
        state.ticket_reused = True
        state.ticket_association = "reused"
        output_summary = f"approval_reused:{ticket.ticket_id}"

    return _associate_ticket(db, state, ticket, output_summary)


def _associate_ticket(
    db: Session,
    state: CopilotState,
    ticket: Ticket,
    output_summary: str,
) -> CopilotState:
    run = db.get(AgentRun, state.run_id)
    if run is None:
        raise ValueError(f"Agent run not found: {state.run_id}")
    run.ticket_id = ticket.ticket_id

    state.ticket_id = ticket.ticket_id
    step = record_agent_step(
        db,
        run_id=state.run_id,
        step_name="ticket_create",
        step_type="tool",
        status="success",
        input_summary=state.order.order_id,
        output_summary=output_summary,
    )
    state.steps.append(step)
    return state
