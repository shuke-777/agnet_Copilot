from fastapi import HTTPException
from sqlalchemy.orm import Session

from agents.workflow import run_copilot_workflow
from models.agent_trace import AgentRun
from models.database import SessionLocal
from schemas.copilot import CopilotAnalyzeRequest, CopilotAnalyzeResponse
from services.trace_service import finish_agent_run, start_agent_run
from services.dashboard_cache_service import invalidate_dashboard_cache
from services.risk_ranking_service import refresh_risk_rankings
from services.session_memory_service import SessionMemoryService
from services.operation_log_service import record_operation_log


def start_after_sales_issue(
    db: Session,
    payload: CopilotAnalyzeRequest,
) -> AgentRun:
    run = start_agent_run(
        db,
        session_id=payload.session_id,
        user_id=payload.user_id,
        user_message=payload.user_message,
    )
    record_operation_log(
        db,
        operator="agent",
        operator_type="agent",
        action="copilot_analyze_started",
        target_type="agent_run",
        target_id=run.run_id,
        run_id=run.run_id,
        source="copilot",
        status="running",
        summary="Copilot 分析已启动。",
    )
    db.commit()
    return run


def analyze_after_sales_issue(
    db: Session,
    payload: CopilotAnalyzeRequest,
) -> CopilotAnalyzeResponse:
    run = start_after_sales_issue(db, payload)
    return execute_after_sales_issue(db, payload, run.run_id)


def execute_after_sales_issue(
    db: Session,
    payload: CopilotAnalyzeRequest,
    run_id: str,
) -> CopilotAnalyzeResponse:
    session_memory = SessionMemoryService.from_environment()
    try:
        state = run_copilot_workflow(
            db=db,
            payload=payload,
            run_id=run_id,
            session_context=session_memory.get_context(
                session_id=payload.session_id,
                user_id=payload.user_id,
            ),
        )
        run = db.get(AgentRun, run_id)
        if run is None:
            raise ValueError(f"Agent run not found: {run_id}")
        run.intent = state.intent
        run.order_id = state.order_id
        session_memory.append_turn(
            session_id=payload.session_id,
            user_id=payload.user_id,
            user_message=payload.user_message,
            assistant_message=state.reply_draft or "",
            order_id=state.order_id,
        )
        invalidate_dashboard_cache()
        refresh_risk_rankings(db)
        response = CopilotAnalyzeResponse(
            run_id=run.run_id,
            intent=state.intent or "unknown",
            order_id=state.order_id or "",
            is_abnormal=bool(state.is_abnormal),
            reply_draft=state.reply_draft or "",
            ticket_created=state.ticket_created,
            ticket_reused=state.ticket_reused,
            ticket_association=state.ticket_association,
            ticket_id=state.ticket_id,
            approval_required=state.approval_required,
            approval_status=state.approval_status,
            approval_reason=state.approval_reason,
            feishu_status=state.feishu_status,
            policy_sources=state.retrieved_policies,
        )
        run.result_payload = response.model_dump_json()
        record_operation_log(
            db,
            operator="agent",
            operator_type="agent",
            action="copilot_analyze_completed",
            target_type="agent_run",
            target_id=run.run_id,
            ticket_id=state.ticket_id,
            run_id=run.run_id,
            order_id=state.order_id,
            source="copilot",
            status="success",
            summary="Copilot 分析完成。",
            after_data={"intent": state.intent, "ticket_id": state.ticket_id},
        )
        finish_agent_run(db, run_id=run.run_id, status="success")
        return response
    except HTTPException:
        record_operation_log(
            db,
            operator="agent",
            operator_type="agent",
            action="copilot_analyze_failed",
            target_type="agent_run",
            target_id=run_id,
            run_id=run_id,
            source="copilot",
            status="failed",
            summary="Copilot 分析失败。",
        )
        finish_agent_run(db, run_id=run_id, status="failed")
        invalidate_dashboard_cache()
        refresh_risk_rankings(db)
        raise
    except Exception as exc:
        record_operation_log(
            db,
            operator="agent",
            operator_type="agent",
            action="copilot_analyze_failed",
            target_type="agent_run",
            target_id=run_id,
            run_id=run_id,
            source="copilot",
            status="failed",
            summary="Copilot 分析失败。",
            extra_data={"error_type": type(exc).__name__},
        )
        finish_agent_run(db, run_id=run_id, status="failed")
        invalidate_dashboard_cache()
        refresh_risk_rankings(db)
        raise exc


def run_after_sales_issue_background(payload: CopilotAnalyzeRequest, run_id: str) -> None:
    with SessionLocal() as db:
        try:
            execute_after_sales_issue(db, payload, run_id)
        except Exception:
            # The run has already been marked failed by execute_after_sales_issue.
            # Background tasks must not crash the ASGI response lifecycle.
            db.rollback()
