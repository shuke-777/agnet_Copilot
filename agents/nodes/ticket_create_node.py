from sqlalchemy.orm import Session

from agents.state import CopilotState
from api.business import make_id
from models.business import Ticket
from services.trace_service import record_agent_step


def ticket_create_node(db: Session, state: CopilotState) -> CopilotState:
    if state.intent != "logistics_delay" or not state.is_abnormal:
        return state

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
        output_summary=ticket.ticket_id,
    )
    state.steps.append(step)
    return state
