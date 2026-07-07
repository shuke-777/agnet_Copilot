from fastapi import HTTPException
from sqlalchemy.orm import Session

from agents.workflow import run_copilot_workflow
from schemas.copilot import CopilotAnalyzeRequest, CopilotAnalyzeResponse
from services.trace_service import finish_agent_run, start_agent_run


def analyze_after_sales_issue(
    db: Session,
    payload: CopilotAnalyzeRequest,
) -> CopilotAnalyzeResponse:
    run = start_agent_run(
        db,
        session_id=payload.session_id,
        user_id=payload.user_id,
        user_message=payload.user_message,
    )

    try:
        state = run_copilot_workflow(db=db, payload=payload, run_id=run.run_id)
        run.intent = state.intent
        db.commit()
        finish_agent_run(db, run_id=run.run_id, status="success")
        return CopilotAnalyzeResponse(
            run_id=run.run_id,
            intent=state.intent or "unknown",
            order_id=state.order_id or "",
            is_abnormal=bool(state.is_abnormal),
            reply_draft=state.reply_draft or "",
            ticket_created=state.ticket_id is not None,
            ticket_id=state.ticket_id,
        )
    except HTTPException:
        finish_agent_run(db, run_id=run.run_id, status="failed")
        raise
    except Exception as exc:
        finish_agent_run(db, run_id=run.run_id, status="failed")
        raise exc
