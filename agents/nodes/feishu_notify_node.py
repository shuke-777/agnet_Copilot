from sqlalchemy.orm import Session

from agents.state import CopilotState
from models.business import Ticket
from services.feishu_service import (
    build_feishu_approval_card_payload,
    build_feishu_approval_message,
    build_feishu_ticket_message,
    send_feishu_app_bot_card_notification,
    send_feishu_text_notification,
)
from services.trace_service import record_agent_step


def feishu_notify_node(db: Session, state: CopilotState) -> CopilotState:
    if state.approval_required and state.approval_status == "pending":
        ticket = db.get(Ticket, state.ticket_id) if state.ticket_id else None
        if state.order is None:
            state.feishu_status = "failed"
            step = record_agent_step(
                db,
                run_id=state.run_id,
                step_name="feishu_notify",
                step_type="webhook",
                status="failed",
                input_summary=state.order_id,
                output_summary="飞书待审核通知上下文缺失",
                error_message="Order not found",
            )
            state.steps.append(step)
            return state

        if ticket is not None:
            payload = build_feishu_approval_card_payload(
                ticket=ticket,
                order=state.order,
                applicant=ticket.created_by,
                approval_reason=state.approval_reason,
                suggested_action=ticket.suggested_action,
            )
            result = send_feishu_app_bot_card_notification(payload)
            if result.status == "disabled":
                message = build_feishu_approval_message(
                    order=state.order,
                    response_level="高" if ticket.priority == "high" else "普通",
                    applicant=ticket.created_by,
                    approval_reason=state.approval_reason or "涉及高风险售后动作，需要人工审核",
                    suggested_action=ticket.suggested_action,
                    requested_at=ticket.created_at,
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
                    input_summary=ticket.ticket_id,
                    output_summary=f"降级为 Webhook 待审核通知：{result.message}",
                    error_message=result.message if result.status == "failed" else None,
                )
                state.steps.append(step)
                return state

            state.feishu_status = result.status
            step = record_agent_step(
                db,
                run_id=state.run_id,
                step_name="feishu_notify",
                step_type="feishu_app_bot",
                status=result.status,
                input_summary=ticket.ticket_id,
                output_summary=f"自建应用审核卡片：{result.message}",
                error_message=result.message if result.status == "failed" else None,
            )
            state.steps.append(step)
            return state

        message = build_feishu_approval_message(
            order=state.order,
            response_level="高",
            applicant="agent",
            approval_reason=state.approval_reason,
            suggested_action=state.reply_draft or "请人工审核本次售后处理建议。",
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
            input_summary=state.order.order_id,
            output_summary=f"待审核通知：{result.message}",
            error_message=result.message if result.status == "failed" else None,
        )
        state.steps.append(step)
        return state

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
        output_summary = (
            "已关联会话主工单，跳过飞书新建工单通知"
            if state.ticket_association == "session_linked"
            else "复用已有未关闭工单，跳过飞书新建工单通知"
        )
        step = record_agent_step(
            db,
            run_id=state.run_id,
            step_name="feishu_notify",
            step_type="webhook",
            status="skipped",
            input_summary=state.ticket_id,
            output_summary=output_summary,
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
