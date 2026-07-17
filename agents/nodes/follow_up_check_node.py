from sqlalchemy.orm import Session

from agents.state import CopilotState
from services.trace_service import record_agent_step


FOLLOW_UP_PHRASES = (
    "催一下",
    "催物流",
    "催快递",
    "继续催",
    "继续跟进",
    "帮我跟进",
    "帮我催",
    "加急",
    "尽快处理",
    "联系快递",
    "联系物流",
)


def follow_up_check_node(db: Session, state: CopilotState) -> CopilotState:
    state.follow_up_requested = any(
        phrase in state.payload.user_message for phrase in FOLLOW_UP_PHRASES
    )
    step = record_agent_step(
        db,
        run_id=state.run_id,
        step_name="follow_up_check",
        step_type="rule",
        status="success",
        input_summary=state.payload.user_message,
        output_summary="requested" if state.follow_up_requested else "not_requested",
    )
    state.steps.append(step)
    return state
