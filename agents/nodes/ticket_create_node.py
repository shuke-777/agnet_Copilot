from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.state import CopilotState
from api.business import make_id
from models.agent_trace import AgentRun
from models.business import Ticket, TicketEvent, utc_now
from services.trace_service import record_agent_step


def ticket_create_node(db: Session, state: CopilotState) -> CopilotState:
    if state.intent != "logistics_delay" or not state.is_abnormal:
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
        state.ticket_created = True
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
        state.ticket_reused = True
        output_summary = f"reused:{ticket.ticket_id}"

    run = db.get(AgentRun, state.run_id)
    if run is None:
        raise ValueError(f"Agent run not found: {state.run_id}")
    run.ticket_id = ticket.ticket_id
    db.commit()
    db.refresh(ticket)

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
