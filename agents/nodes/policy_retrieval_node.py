from sqlalchemy.orm import Session

from agents.state import CopilotState
from services.policy_service import retrieve_policy_candidates
from services.trace_service import record_agent_step


def build_policy_query(state: CopilotState) -> str:
    parts = [
        state.rewritten_query or state.payload.user_message,
        state.logistics.status if state.logistics else "",
        state.logistics.last_event if state.logistics else "",
        "物流异常" if state.is_abnormal else "物流正常",
    ]
    return " ".join(part for part in parts if part)


def policy_retrieval_node(db: Session, state: CopilotState) -> CopilotState:
    query = build_policy_query(state)
    state.policy_candidates = retrieve_policy_candidates(query)
    step = record_agent_step(
        db,
        run_id=state.run_id,
        step_name="policy_retrieval",
        step_type="rag",
        status="success",
        input_summary=query,
        output_summary=f"召回 {len(state.policy_candidates)} 条候选售后知识",
    )
    state.steps.append(step)
    return state
