from sqlalchemy.orm import Session

from agents.state import CopilotState
from schemas.llm import IntentRecognitionResult
from services.llm_gateway import LLMGateway
from services.trace_service import record_agent_step


VALID_INTENTS = {
    "refund",
    "return",
    "freight",
    "shipping_timeliness",
    "exchange",
    "address_change",
    "cancel_order",
    "compensation",
    "logistics_delay",
    "logistics_query",
    "unknown",
}


def recognize_intent(user_message: str) -> str:
    if any(keyword in user_message for keyword in ("退款", "退钱", "仅退款")):
        return "refund"
    if any(keyword in user_message for keyword in ("换货", "重发", "补发")):
        return "exchange"
    if any(keyword in user_message for keyword in ("退货", "寄回")):
        return "return"
    if "改地址" in user_message:
        return "address_change"
    if "取消订单" in user_message:
        return "cancel_order"
    if any(keyword in user_message for keyword in ("补偿", "赔付")):
        return "compensation"
    if any(keyword in user_message for keyword in ("运费", "邮费", "运费险")):
        return "freight"
    if any(keyword in user_message for keyword in ("未发货", "什么时候发", "催发货")):
        return "shipping_timeliness"
    delay_keywords = ("没收到", "未收到", "催", "不动", "停滞", "异常", "三天", "72", "96")
    if any(keyword in user_message for keyword in delay_keywords):
        return "logistics_delay"
    if "发货" in user_message:
        return "shipping_timeliness"
    query_keywords = ("物流", "快递", "到哪", "到哪里", "进度", "查一下", "查询", "看一下", "什么情况")
    if any(keyword in user_message for keyword in query_keywords):
        return "logistics_query"
    return "unknown"


def normalize_intent(raw_intent: str | None, user_message: str) -> str:
    fallback_intent = recognize_intent(user_message)
    if raw_intent not in VALID_INTENTS:
        return fallback_intent
    if fallback_intent in {
        "refund",
        "return",
        "exchange",
        "address_change",
        "cancel_order",
        "compensation",
        "freight",
    }:
        return fallback_intent
    if fallback_intent == "logistics_delay" and raw_intent in {"shipping_timeliness", "logistics_query", "unknown"}:
        return "logistics_delay"
    if raw_intent == "unknown" and fallback_intent != "unknown":
        return fallback_intent
    if raw_intent == "logistics_delay" and fallback_intent == "logistics_query":
        return "logistics_query"
    return raw_intent


def intent_node(db: Session, state: CopilotState) -> CopilotState:
    result = LLMGateway.from_environment().complete_structured(
        system_prompt="你是电商售后意图分类器。只返回 JSON：{\"intent\": \"...\"}。",
        user_prompt=(
            "将用户问题分类为 refund、return、exchange、address_change、cancel_order、"
            "compensation、freight、shipping_timeliness、logistics_query、"
            f"logistics_delay 或 unknown：{state.payload.user_message}"
        ),
        response_model=IntentRecognitionResult,
    )
    raw_intent = result.value.intent if result.success else None
    state.intent = normalize_intent(raw_intent, state.payload.user_message)
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
