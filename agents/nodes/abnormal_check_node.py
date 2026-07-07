from sqlalchemy.orm import Session

from agents.state import CopilotState
from services.trace_service import record_agent_step


def abnormal_check_node(db: Session, state: CopilotState) -> CopilotState:
    state.is_abnormal = bool(state.logistics and state.logistics.is_abnormal)
    step = record_agent_step(
        db,
        run_id=state.run_id,
        step_name="abnormal_check",
        step_type="rule",
        status="success",
        input_summary=state.logistics.status if state.logistics else None,
        output_summary="物流异常" if state.is_abnormal else "物流正常",
    )
    state.steps.append(step)
    return state
