from sqlalchemy.orm import Session

from agents.state import CopilotState
from models.business import Ticket
from services.feishu_service import build_feishu_ticket_message, send_feishu_text_notification
from services.trace_service import record_agent_step


def feishu_notify_node(db: Session, state: CopilotState) -> CopilotState:
    if state.ticket_id is None:
        state.feishu_status = "skipped"
        step = record_agent_step(
            db,
            run_id=state.run_id,
            step_name="feishu_notify",
            step_type="webhook",
            status="skipped",
            input_summary=state.order_id,
            output_summary="未创建工单，跳过飞书通知",
        )
        state.steps.append(step)
        return state

    if not state.ticket_created:
        state.feishu_status = "skipped"
        step = record_agent_step(
            db,
            run_id=state.run_id,
            step_name="feishu_notify",
            step_type="webhook",
            status="skipped",
            input_summary=state.ticket_id,
            output_summary="复用已有未关闭工单，跳过飞书新建工单通知",
        )
        state.steps.append(step)
        return state

    ticket = db.get(Ticket, state.ticket_id)
    if ticket is None or state.order is None or state.logistics is None:
        state.feishu_status = "failed"
        step = record_agent_step(
            db,
            run_id=state.run_id,
            step_name="feishu_notify",
            step_type="webhook",
            status="failed",
            input_summary=state.ticket_id,
            output_summary="飞书通知上下文缺失",
            error_message="Ticket, order, or logistics not found",
        )
        state.steps.append(step)
        return state

    message = build_feishu_ticket_message(
        ticket=ticket,
        order=state.order,
        logistics=state.logistics,
    )
    result = send_feishu_text_notification(message)
    state.feishu_status = result.status
    step_status = "skipped" if result.status == "disabled" else result.status
    step = record_agent_step(
        db,
        run_id=state.run_id,
        step_name="feishu_notify",
        step_type="webhook",
        status=step_status,
        input_summary=state.ticket_id,
        output_summary=result.message,
        error_message=result.message if result.status == "failed" else None,
    )
    state.steps.append(step)
    return state
