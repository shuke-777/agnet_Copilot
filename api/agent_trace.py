import json
import time
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from models.agent_trace import AgentRun, AgentStep
from models.database import SessionLocal, get_db
from schemas.copilot import CopilotAnalyzeResponse
from schemas.agent_trace import AgentRunRead, AgentStepRead
from services.demo_trace_service import create_demo_waterfall_run
from services.dashboard_cache_service import invalidate_dashboard_cache
from services.risk_ranking_service import refresh_risk_rankings


router = APIRouter(prefix="/api", tags=["agent trace"])


def get_run_or_404(db: Session, run_id: str) -> AgentRun:
    run = db.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run not found",
        )
    return run


@router.get("/runs", response_model=list[AgentRunRead])
def list_agent_runs(q: str | None = None, db: Session = Depends(get_db)) -> list[AgentRun]:
    statement = select(AgentRun)
    if q and q.strip():
        query = q.strip().upper()
        statement = statement.where(
            or_(
                AgentRun.run_id.ilike(f"%{query}%"),
                AgentRun.order_id.ilike(f"%{query}%"),
                AgentRun.ticket_id.ilike(f"%{query}%"),
            )
        )
    return list(db.scalars(statement.order_by(AgentRun.created_at.desc())))


@router.post("/runs/demo-waterfall", response_model=AgentRunRead, status_code=status.HTTP_201_CREATED)
def create_demo_waterfall(db: Session = Depends(get_db)) -> AgentRun:
    run = create_demo_waterfall_run(db)
    invalidate_dashboard_cache()
    refresh_risk_rankings(db)
    return run


@router.get("/runs/{run_id}", response_model=AgentRunRead)
def get_agent_run(run_id: str, db: Session = Depends(get_db)) -> AgentRun:
    run = db.scalar(select(AgentRun).where(AgentRun.run_id == run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")
    return run


@router.get("/runs/{run_id}/steps", response_model=list[AgentStepRead])
def list_agent_steps(run_id: str, db: Session = Depends(get_db)) -> list[AgentStep]:
    get_run_or_404(db, run_id)
    return list(
        db.scalars(
            select(AgentStep)
            .where(AgentStep.run_id == run_id)
            .order_by(AgentStep.start_time)
        )
    )


def format_sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def serialize_run(run: AgentRun) -> dict:
    return AgentRunRead.model_validate(run).model_dump(mode="json")


def serialize_step(step: AgentStep) -> dict:
    return AgentStepRead.model_validate(step).model_dump(mode="json")


def stream_run_events(run_id: str, *, poll_interval_seconds: float = 0.2) -> Iterator[str]:
    sent_step_ids: set[str] = set()
    last_heartbeat = time.monotonic()

    with SessionLocal() as db:
        run = get_run_or_404(db, run_id)
        yield format_sse_event("run_started", {"run": serialize_run(run)})

        while True:
            steps = list(
                db.scalars(
                    select(AgentStep)
                    .where(AgentStep.run_id == run_id)
                    .order_by(AgentStep.start_time)
                )
            )
            for step in steps:
                if step.step_id in sent_step_ids:
                    continue
                sent_step_ids.add(step.step_id)
                yield format_sse_event("step_created", {"step": serialize_step(step)})

            db.expire_all()
            run = get_run_or_404(db, run_id)
            if run.status in {"success", "failed"}:
                event_name = "run_finished" if run.status == "success" else "run_failed"
                payload = {"run": serialize_run(run)}
                if run.result_payload:
                    payload["result"] = json.loads(run.result_payload)
                yield format_sse_event(event_name, payload)
                break

            now = time.monotonic()
            if now - last_heartbeat >= 2:
                last_heartbeat = now
                yield format_sse_event("heartbeat", {"run_id": run_id, "status": run.status})

            time.sleep(poll_interval_seconds)


@router.get("/runs/{run_id}/events")
def get_agent_run_events(run_id: str, db: Session = Depends(get_db)) -> StreamingResponse:
    get_run_or_404(db, run_id)
    return StreamingResponse(
        stream_run_events(run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/runs/{run_id}/result", response_model=CopilotAnalyzeResponse)
def get_agent_run_result(run_id: str, db: Session = Depends(get_db)) -> CopilotAnalyzeResponse:
    run = get_run_or_404(db, run_id)
    if not run.result_payload:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run result not found",
        )
    return CopilotAnalyzeResponse.model_validate_json(run.result_payload)
