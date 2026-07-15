import re

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from agents.state import CopilotState
from models.agent_trace import AgentRun
from schemas.llm import OrderExtractionResult
from services.llm_gateway import LLMGateway
from services.trace_service import record_agent_step


ORDER_ID_PATTERN = re.compile(r"\bORD-\d+\b", re.IGNORECASE)


def extract_order_id(user_message: str) -> str | None:
    match = ORDER_ID_PATTERN.search(user_message)
    if match is None:
        return None
    return match.group(0).upper()


def order_extract_node(db: Session, state: CopilotState) -> CopilotState:
    result = LLMGateway.from_environment().complete_structured(
        system_prompt="你从电商售后问题中提取订单号。只返回 JSON：{\"order_id\": \"ORD-数字\"}；没有则返回 null。",
        user_prompt=state.payload.user_message,
        response_model=OrderExtractionResult,
    )
    state.order_id = result.value.order_id if result.success else extract_order_id(state.payload.user_message)
    if state.order_id is None:
        history_messages = [message.content for message in reversed(state.payload.history) if message.role == "user"]
        memory_messages = [message.content for message in reversed(state.session_context.messages) if message.role == "user"]
        prior_session_messages = list(
            db.scalars(
                select(AgentRun.user_message)
                .where(AgentRun.session_id == state.payload.session_id, AgentRun.run_id != state.run_id)
                .order_by(AgentRun.created_at.desc())
                .limit(5)
            )
        )
        for message in [*history_messages, *memory_messages, *prior_session_messages]:
            state.order_id = extract_order_id(message)
            if state.order_id is not None:
                break
    if state.order_id is None:
        state.order_id = state.session_context.order_id
    if state.order_id is None:
        step = record_agent_step(
            db,
            run_id=state.run_id,
            step_name="order_extract",
            step_type="agent",
            status="failed",
            input_summary=state.payload.user_message,
            output_summary="未识别到订单号",
            error_message="Order id not found in user message",
            llm_provider=result.call.provider,
            llm_model=result.call.model,
            input_tokens=result.call.input_tokens,
            output_tokens=result.call.output_tokens,
            fallback_reason=result.call.fallback_reason,
            duration_override_ms=result.call.duration_ms,
        )
        state.steps.append(step)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order id not found in user message",
        )

    step = record_agent_step(
        db,
        run_id=state.run_id,
        step_name="order_extract",
        step_type="agent",
        status="success",
        input_summary=state.payload.user_message,
        output_summary=state.order_id,
        llm_provider=result.call.provider,
        llm_model=result.call.model,
        input_tokens=result.call.input_tokens,
        output_tokens=result.call.output_tokens,
        fallback_reason=result.call.fallback_reason,
        duration_override_ms=result.call.duration_ms,
    )
    state.steps.append(step)
    return state
