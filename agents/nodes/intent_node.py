from sqlalchemy.orm import Session

from agents.state import CopilotState
from schemas.llm import IntentRecognitionResult
from services.llm_gateway import LLMGateway
from services.trace_service import record_agent_step


def recognize_intent(user_message: str) -> str:
    if any(keyword in user_message for keyword in ("退款", "退钱", "仅退款")):
        return "refund"
    if any(keyword in user_message for keyword in ("退货", "换货", "寄回")):
        return "return"
    if any(keyword in user_message for keyword in ("运费", "邮费", "运费险")):
        return "freight"
    if any(keyword in user_message for keyword in ("发货", "未发货", "什么时候发")):
        return "shipping_timeliness"
    keywords = ("没收到", "未收到", "物流", "快递", "催")
    if any(keyword in user_message for keyword in keywords):
        return "logistics_delay"
    return "unknown"


def intent_node(db: Session, state: CopilotState) -> CopilotState:
    result = LLMGateway.from_environment().complete_structured(
        system_prompt="你是电商售后意图分类器。只返回 JSON：{\"intent\": \"...\"}。",
        user_prompt=(
            "将用户问题分类为 refund、return、freight、shipping_timeliness、"
            f"logistics_delay 或 unknown：{state.payload.user_message}"
        ),
        response_model=IntentRecognitionResult,
    )
    state.intent = result.value.intent if result.success else recognize_intent(state.payload.user_message)
    step = record_agent_step(
        db,
        run_id=state.run_id,
        step_name="intent_recognition",
        step_type="agent",
        status="success",
        input_summary=state.payload.user_message,
        output_summary=state.intent,
        llm_provider=result.call.provider,
        llm_model=result.call.model,
        input_tokens=result.call.input_tokens,
        output_tokens=result.call.output_tokens,
        fallback_reason=result.call.fallback_reason,
        duration_override_ms=result.call.duration_ms,
    )
    state.steps.append(step)
    return state
