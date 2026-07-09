from sqlalchemy.orm import Session

from agents.state import CopilotState
from services.policy_service import retrieve_after_sales_policies
from services.trace_service import record_agent_step


def build_policy_query(state: CopilotState) -> str:
    parts = [
        state.payload.user_message,
        state.logistics.status if state.logistics else "",
        state.logistics.last_event if state.logistics else "",
        "物流异常" if state.is_abnormal else "物流正常",
    ]
    return " ".join(part for part in parts if part)


def policy_retrieval_node(db: Session, state: CopilotState) -> CopilotState:
    query = build_policy_query(state)
    state.retrieved_policies = retrieve_after_sales_policies(
        query=query,
        is_abnormal=state.is_abnormal,
    )
    output_summary = "、".join(policy.title for policy in state.retrieved_policies)
    step = record_agent_step(
        db,
        run_id=state.run_id,
        step_name="policy_retrieval",
        step_type="rag",
        status="success",
        input_summary=query,
        output_summary=output_summary or "未召回相关售后知识",
    )
    state.steps.append(step)
    return state
