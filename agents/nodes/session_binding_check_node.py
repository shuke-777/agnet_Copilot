from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from agents.state import CopilotState
from services.session_ticket_binding_service import (
    SessionBindingDataError,
    SessionTicketBindingService,
)
from services.trace_service import record_agent_step


def session_binding_check_node(db: Session, state: CopilotState) -> CopilotState:
    service = SessionTicketBindingService(db)
    binding = service.get_binding(
        session_id=state.payload.session_id,
        user_id=state.payload.user_id,
    )
    if binding is None:
        output_summary = "无会话绑定"
    elif binding.order_id != state.order_id:
        step = record_agent_step(
            db,
            run_id=state.run_id,
            step_name="session_binding_check",
            step_type="rule",
            status="failed",
            input_summary=state.order_id,
            output_summary=f"会话已绑定订单 {binding.order_id}",
            error_message="Session order mismatch",
        )
        state.steps.append(step)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "session_order_mismatch",
                "bound_order_id": binding.order_id,
                "requested_order_id": state.order_id,
            },
        )
    else:
        try:
            state.active_session_ticket = service.get_active_ticket(
                session_id=state.payload.session_id,
                user_id=state.payload.user_id,
            )
        except SessionBindingDataError as exc:
            step = record_agent_step(
                db,
                run_id=state.run_id,
                step_name="session_binding_check",
                step_type="rule",
                status="failed",
                input_summary=state.order_id,
                output_summary="会话绑定数据不一致",
                error_message=str(exc),
            )
            state.steps.append(step)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "session_binding_data_error"},
            ) from exc
        output_summary = (
            f"存在同订单活动工单 {state.active_session_ticket.ticket_id}"
            if state.active_session_ticket is not None
            else "同订单绑定的工单已非活动状态"
        )

    step = record_agent_step(
        db,
        run_id=state.run_id,
        step_name="session_binding_check",
        step_type="rule",
        status="success",
        input_summary=state.order_id,
        output_summary=output_summary,
    )
    state.steps.append(step)
    return state
