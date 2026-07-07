from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.state import CopilotState
from models.business import Logistics
from services.trace_service import record_agent_step


def logistics_query_node(db: Session, state: CopilotState) -> CopilotState:
    state.logistics = db.scalar(select(Logistics).where(Logistics.order_id == state.order_id))
    if state.logistics is None:
        step = record_agent_step(
            db,
            run_id=state.run_id,
            step_name="logistics_query",
            step_type="tool",
            status="failed",
            input_summary=state.order_id,
            output_summary="物流不存在",
            error_message="Logistics not found",
        )
        state.steps.append(step)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Logistics not found",
        )

    step = record_agent_step(
        db,
        run_id=state.run_id,
        step_name="logistics_query",
        step_type="tool",
        status="success",
        input_summary=state.order_id,
        output_summary=state.logistics.last_event,
    )
    state.steps.append(step)
    return state
