from sqlalchemy.orm import Session

from agents.state import CopilotState
from services.policy_service import rerank_after_sales_policies
from services.rag_cache_service import RagCache
from services.trace_service import record_agent_step


def policy_rerank_node(db: Session, state: CopilotState) -> CopilotState:
    cache = state.rag_cache or RagCache.from_environment()
    state.rag_cache = cache
    cached = cache.get_or_load_policy_rerank(
        user_message=state.payload.user_message,
        intent=state.intent,
        is_abnormal=state.is_abnormal,
        loader=lambda: rerank_after_sales_policies(
            query=state.rewritten_query or state.payload.user_message,
            candidates=state.policy_candidates,
            intent=state.intent,
            is_abnormal=state.is_abnormal,
        ),
    )
    state.retrieved_policies = cached.value
    output_summary = "、".join(policy.title for policy in state.retrieved_policies)
    step = record_agent_step(
        db,
        run_id=state.run_id,
        step_name="policy_rerank",
        step_type="rag",
        status="success",
        input_summary=f"候选知识 {len(state.policy_candidates)} 条",
        output_summary=output_summary or "未召回相关售后知识",
        cache_hit=cached.cache_hit,
    )
    state.steps.append(step)
    return state
