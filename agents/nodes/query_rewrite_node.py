from sqlalchemy.orm import Session

from agents.state import CopilotState
from schemas.llm import QueryRewriteResult
from services.llm_gateway import LLMGateway
from services.policy_service import rewrite_after_sales_query
from services.rag_cache_service import RagCache
from services.trace_service import record_agent_step


def query_rewrite_node(db: Session, state: CopilotState) -> CopilotState:
    fallback_query = rewrite_after_sales_query(
        state.payload.user_message,
        intent=state.intent,
        is_abnormal=state.is_abnormal,
    )
    result = None

    def load_rewritten_query() -> str:
        nonlocal result
        result = LLMGateway.from_environment().complete_structured(
            system_prompt="你为电商售后 RAG 改写检索问题。只返回 JSON：{\"rewritten_query\": \"...\"}。保留订单号和售后意图。",
            user_prompt=(
                f"用户问题：{state.payload.user_message}\n意图：{state.intent}\n"
                f"物流异常：{state.is_abnormal}\n请生成检索问题。"
            ),
            response_model=QueryRewriteResult,
        )
        return result.value.rewritten_query if result.success else fallback_query

    cache = state.rag_cache or RagCache.from_environment()
    state.rag_cache = cache
    cached = cache.get_or_load_query_rewrite(
        user_message=state.payload.user_message,
        intent=state.intent,
        is_abnormal=state.is_abnormal,
        loader=load_rewritten_query,
    )
    state.rewritten_query = cached.value
    step = record_agent_step(
        db,
        run_id=state.run_id,
        step_name="query_rewrite",
        step_type="rag",
        status="success",
        input_summary=state.payload.user_message,
        output_summary=state.rewritten_query,
        llm_provider=result.call.provider if result else None,
        llm_model=result.call.model if result else None,
        input_tokens=result.call.input_tokens if result else None,
        output_tokens=result.call.output_tokens if result else None,
        fallback_reason=result.call.fallback_reason if result else None,
        duration_override_ms=result.call.duration_ms if result else None,
        cache_hit=cached.cache_hit,
    )
    state.steps.append(step)
    return state
