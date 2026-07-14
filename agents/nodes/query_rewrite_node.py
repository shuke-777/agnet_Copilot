from sqlalchemy.orm import Session

from agents.state import CopilotState
from schemas.llm import QueryRewriteResult
from services.llm_gateway import LLMGateway
from services.policy_service import rewrite_after_sales_query
from services.trace_service import record_agent_step


def query_rewrite_node(db: Session, state: CopilotState) -> CopilotState:
    fallback_query = rewrite_after_sales_query(
        state.payload.user_message,
        intent=state.intent,
        is_abnormal=state.is_abnormal,
    )
    result = LLMGateway.from_environment().complete_structured(
        system_prompt="你为电商售后 RAG 改写检索问题。只返回 JSON：{\"rewritten_query\": \"...\"}。保留订单号和售后意图。",
        user_prompt=(
            f"用户问题：{state.payload.user_message}\n意图：{state.intent}\n"
            f"物流异常：{state.is_abnormal}\n请生成检索问题。"
        ),
        response_model=QueryRewriteResult,
    )
    state.rewritten_query = result.value.rewritten_query if result.success else fallback_query
    step = record_agent_step(
        db,
        run_id=state.run_id,
        step_name="query_rewrite",
        step_type="rag",
        status="success",
        input_summary=state.payload.user_message,
        output_summary=state.rewritten_query,
        llm_provider=result.call.provider,
        llm_model=result.call.model,
        input_tokens=result.call.input_tokens,
        output_tokens=result.call.output_tokens,
        fallback_reason=result.call.fallback_reason,
        duration_override_ms=result.call.duration_ms,
    )
    state.steps.append(step)
    return state
