from sqlalchemy.orm import Session

from agents.state import CopilotState
from services.trace_service import record_agent_step


REVIEW_REQUIRED_INTENTS = {
    "refund",
    "return",
    "exchange",
    "address_change",
    "cancel_order",
    "compensation",
}
REVIEW_REQUIRED_KEYWORDS = ("退款", "退钱", "退货", "补偿", "赔付", "重发", "补发", "改地址", "取消订单")
INTENT_LABELS = {
    "refund": "退款",
    "return": "退货",
    "exchange": "换货/补发",
    "address_change": "改地址",
    "cancel_order": "取消订单",
    "compensation": "补偿/赔付",
}


def evaluate_approval(state: CopilotState) -> tuple[bool, str, str]:
    user_message = state.payload.user_message
    if state.intent in REVIEW_REQUIRED_INTENTS:
        intent_label = INTENT_LABELS.get(state.intent or "", state.intent or "售后处理")
        return True, "pending", f"{intent_label}涉及资金、库存或权益变更，需要人工审核"
    if any(keyword in user_message for keyword in REVIEW_REQUIRED_KEYWORDS):
        return True, "pending", "用户诉求涉及资金、库存或权益变更，需要人工审核"
    return False, "not_required", "物流催办不涉及资金、库存或权益变更"


def approval_check_node(db: Session, state: CopilotState) -> CopilotState:
    required, approval_status, approval_reason = evaluate_approval(state)
    state.approval_required = required
    state.approval_status = approval_status
    state.approval_reason = approval_reason
    step = record_agent_step(
        db,
        run_id=state.run_id,
        step_name="approval_check",
        step_type="agent",
        status="success",
        input_summary=state.intent,
        output_summary=f"{approval_status}:{approval_reason}",
    )
    state.steps.append(step)
    return state
