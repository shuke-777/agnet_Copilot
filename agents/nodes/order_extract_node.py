import re

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from agents.state import CopilotState
from services.trace_service import record_agent_step


ORDER_ID_PATTERN = re.compile(r"\bORD-\d+\b", re.IGNORECASE)


def extract_order_id(user_message: str) -> str | None:
    match = ORDER_ID_PATTERN.search(user_message)
    if match is None:
        return None
    return match.group(0).upper()


def order_extract_node(db: Session, state: CopilotState) -> CopilotState:
    state.order_id = extract_order_id(state.payload.user_message)
    if state.order_id is None:
        step = record_agent_step(
            db,
            run_id=state.run_id,
            step_name="order_extract",
            step_type="agent",
            status="failed",
            input_summary=state.payload.user_message,
            output_summary="未识别到订单号",
            error_message="Order id not found in user message",
        )
        state.steps.append(step)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order id not found in user message",
        )

    step = record_agent_step(
        db,
        run_id=state.run_id,
        step_name="order_extract",
        step_type="agent",
        status="success",
        input_summary=state.payload.user_message,
        output_summary=state.order_id,
    )
    state.steps.append(step)
    return state
