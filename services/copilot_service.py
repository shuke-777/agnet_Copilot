from fastapi import HTTPException
from sqlalchemy.orm import Session

from agents.workflow import run_copilot_workflow
from schemas.copilot import CopilotAnalyzeRequest, CopilotAnalyzeResponse
from services.trace_service import finish_agent_run, start_agent_run
from services.dashboard_cache_service import invalidate_dashboard_cache
from services.session_memory_service import SessionMemoryService


def analyze_after_sales_issue(
    db: Session,
    payload: CopilotAnalyzeRequest,
) -> CopilotAnalyzeResponse:
    session_memory = SessionMemoryService.from_environment()
    run = start_agent_run(
        db,
        session_id=payload.session_id,
        user_id=payload.user_id,
        user_message=payload.user_message,
    )

    try:
        state = run_copilot_workflow(
            db=db,
            payload=payload,
            run_id=run.run_id,
            session_context=session_memory.get_context(
                session_id=payload.session_id,
                user_id=payload.user_id,
            ),
        )
        run.intent = state.intent
        run.order_id = state.order_id
        db.commit()
        finish_agent_run(db, run_id=run.run_id, status="success")
        session_memory.append_turn(
            session_id=payload.session_id,
            user_id=payload.user_id,
            user_message=payload.user_message,
            assistant_message=state.reply_draft or "",
            order_id=state.order_id,
        )
        invalidate_dashboard_cache()
        return CopilotAnalyzeResponse(
            run_id=run.run_id,
            intent=state.intent or "unknown",
            order_id=state.order_id or "",
            is_abnormal=bool(state.is_abnormal),
            reply_draft=state.reply_draft or "",
            ticket_created=state.ticket_created,
            ticket_reused=state.ticket_reused,
            ticket_id=state.ticket_id,
            feishu_status=state.feishu_status,
            policy_sources=state.retrieved_policies,
        )
    except HTTPException:
        finish_agent_run(db, run_id=run.run_id, status="failed")
        invalidate_dashboard_cache()
        raise
    except Exception as exc:
        finish_agent_run(db, run_id=run.run_id, status="failed")
        invalidate_dashboard_cache()
        raise exc
