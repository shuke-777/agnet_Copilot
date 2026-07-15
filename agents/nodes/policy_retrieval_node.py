from sqlalchemy.orm import Session

from agents.state import CopilotState
from services.policy_service import retrieve_policy_candidates
from services.rag_cache_service import RagCache
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
    cache = state.rag_cache or RagCache.from_environment()
    state.rag_cache = cache
    cached = cache.get_or_load_policy_candidates(
        user_message=state.payload.user_message,
        intent=state.intent,
        is_abnormal=state.is_abnormal,
        loader=lambda: retrieve_policy_candidates(query),
    )
    state.policy_candidates = cached.value
    step = record_agent_step(
        db,
        run_id=state.run_id,
        step_name="policy_retrieval",
        step_type="rag",
        status="success",
        input_summary=query,
        output_summary=f"召回 {len(state.policy_candidates)} 条候选售后知识",
        cache_hit=cached.cache_hit,
    )
    state.steps.append(step)
    return state
