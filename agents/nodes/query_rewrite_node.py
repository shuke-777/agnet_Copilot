from sqlalchemy.orm import Session

from agents.state import CopilotState
from services.policy_service import rewrite_after_sales_query
from services.trace_service import record_agent_step


def query_rewrite_node(db: Session, state: CopilotState) -> CopilotState:
    state.rewritten_query = rewrite_after_sales_query(
        state.payload.user_message,
        intent=state.intent,
        is_abnormal=state.is_abnormal,
    )
    step = record_agent_step(
        db,
        run_id=state.run_id,
        step_name="query_rewrite",
        step_type="rag",
        status="success",
        input_summary=state.payload.user_message,
        output_summary=state.rewritten_query,
    )
    state.steps.append(step)
    return state
