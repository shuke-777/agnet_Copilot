from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from agents.state import CopilotState
from models.business import Order
from services.trace_service import record_agent_step


def order_query_node(db: Session, state: CopilotState) -> CopilotState:
    state.order = db.get(Order, state.order_id)
    if state.order is None:
        step = record_agent_step(
            db,
            run_id=state.run_id,
            step_name="order_query",
            step_type="tool",
            status="failed",
            input_summary=state.order_id,
            output_summary="订单不存在",
            error_message="Order not found",
        )
        state.steps.append(step)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    step = record_agent_step(
        db,
        run_id=state.run_id,
        step_name="order_query",
        step_type="tool",
        status="success",
        input_summary=state.order_id,
        output_summary=f"{state.order.product_name} / {state.order.status}",
    )
    state.steps.append(step)
    return state
