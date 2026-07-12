from sqlalchemy.orm import Session

from agents.state import CopilotState
from services.trace_service import record_agent_step


def build_policy_hint(state: CopilotState) -> str:
    if not state.retrieved_policies:
        return ""
    policy_titles = "、".join(policy.title for policy in state.retrieved_policies)
    return f" 参考售后知识：{policy_titles}。"


def build_reply_draft(state: CopilotState) -> str:
    policy_hint = build_policy_hint(state)
    if state.intent == "refund":
        return (
            f"您好，已收到您关于订单 {state.order.order_id} 的退款咨询。"
            "我们会先核实订单和售后申请状态，再向您同步可处理方式与预计时效。"
            f"{policy_hint}"
        )
    if state.intent == "return":
        return (
            f"您好，已收到您关于订单 {state.order.order_id} 的退货咨询。"
            "我们会先核实商品是否满足退货条件，再向您说明申请和寄回要求。"
            f"{policy_hint}"
        )
    if state.intent == "freight":
        return (
            f"您好，已收到您关于订单 {state.order.order_id} 的运费咨询。"
            "我们会根据订单和售后原因核实运费承担规则后回复您。"
            f"{policy_hint}"
        )
    if state.intent == "shipping_timeliness":
        return (
            f"您好，已收到您关于订单 {state.order.order_id} 的发货时效咨询。"
            "我们会核实订单状态，并向您同步确认后的预计发货时间。"
            f"{policy_hint}"
        )
    if state.is_abnormal:
        return (
            f"您好，已为您查询订单 {state.order.order_id} 的物流信息："
            f"{state.logistics.last_event} 我们将为您创建催物流工单，并尽快跟进处理进展。"
            f"{policy_hint}"
        )
    return (
        f"您好，已为您查询订单 {state.order.order_id} 的物流信息，当前物流状态正常："
        f"{state.logistics.last_event} 如后续长时间未更新，您可以继续联系我们。"
        f"{policy_hint}"
    )


def reply_generate_node(db: Session, state: CopilotState) -> CopilotState:
    state.reply_draft = build_reply_draft(state)
    step = record_agent_step(
        db,
        run_id=state.run_id,
        step_name="reply_generate",
        step_type="agent",
        status="success",
        input_summary=state.retrieved_policies[0].title if state.retrieved_policies else None,
        output_summary=state.reply_draft,
    )
    state.steps.append(step)
    return state
