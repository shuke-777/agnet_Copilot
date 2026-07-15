from uuid import uuid4

from sqlalchemy.orm import Session

from models.agent_trace import AgentRun, AgentStep
from models.business import utc_now


def make_trace_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8].upper()}"


def duration_ms(start, end) -> int:
    return int((end - start).total_seconds() * 1000)


def start_agent_run(
    db: Session,
    *,
    session_id: str,
    user_message: str,
    user_id: str | None = None,
    intent: str | None = None,
) -> AgentRun:
    run = AgentRun(
        run_id=make_trace_id("RUN"),
        session_id=session_id,
        user_id=user_id,
        user_message=user_message,
        intent=intent,
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def record_agent_step(
    db: Session,
    *,
    run_id: str,
    step_name: str,
    step_type: str,
    status: str,
    input_summary: str | None = None,
    output_summary: str | None = None,
    error_message: str | None = None,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    fallback_reason: str | None = None,
    cache_hit: bool = False,
    duration_override_ms: int | None = None,
) -> AgentStep:
    start_time = utc_now()
    end_time = utc_now()
    step = AgentStep(
        step_id=make_trace_id("STP"),
        run_id=run_id,
        step_name=step_name,
        step_type=step_type,
        status=status,
        start_time=start_time,
        end_time=end_time,
        duration_ms=duration_override_ms if duration_override_ms is not None else duration_ms(start_time, end_time),
        input_summary=input_summary,
        output_summary=output_summary,
        error_message=error_message,
        llm_provider=llm_provider,
        llm_model=llm_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        fallback_reason=fallback_reason,
        cache_hit=cache_hit,
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


def finish_agent_run(db: Session, *, run_id: str, status: str) -> AgentRun:
    run = db.get(AgentRun, run_id)
    if run is None:
        raise ValueError(f"Agent run not found: {run_id}")

    finished_at = utc_now()
    run.status = status
    run.finished_at = finished_at
    run.total_duration_ms = duration_ms(run.created_at, finished_at)
    db.commit()
    db.refresh(run)
    return run
