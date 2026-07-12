from sqlalchemy.orm import Session

from agents.state import CopilotState
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
    state.intent = recognize_intent(state.payload.user_message)
    step = record_agent_step(
        db,
        run_id=state.run_id,
        step_name="intent_recognition",
        step_type="agent",
        status="success",
        input_summary=state.payload.user_message,
        output_summary=state.intent,
    )
    state.steps.append(step)
    return state
