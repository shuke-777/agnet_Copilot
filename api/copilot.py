from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from models.database import get_db
from schemas.copilot import CopilotAnalyzeRequest, CopilotAnalyzeResponse, CopilotAnalyzeStartResponse
from services.copilot_service import analyze_after_sales_issue, run_after_sales_issue_background, start_after_sales_issue
from services.rate_limit_service import CopilotRateLimiter


router = APIRouter(prefix="/api/copilot", tags=["copilot"])


def enforce_copilot_rate_limit(payload: CopilotAnalyzeRequest, request: Request) -> None:
    subject = payload.user_id or f"ip:{request.client.host if request.client else 'unknown'}"
    rate_limit = CopilotRateLimiter.from_environment().consume(subject)
    if rate_limit.allowed:
        return

    retry_after_seconds = rate_limit.retry_after_seconds
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "code": "copilot_rate_limited",
            "message": "Copilot analysis rate limit exceeded",
            "retry_after_seconds": retry_after_seconds,
        },
        headers={"Retry-After": str(retry_after_seconds)},
    )


@router.post("/analyze", response_model=CopilotAnalyzeResponse)
def analyze_copilot_message(
    payload: CopilotAnalyzeRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> CopilotAnalyzeResponse:
    enforce_copilot_rate_limit(payload, request)
    return analyze_after_sales_issue(db, payload)


@router.post("/analyze/start", response_model=CopilotAnalyzeStartResponse, status_code=status.HTTP_202_ACCEPTED)
def start_copilot_analysis(
    payload: CopilotAnalyzeRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> CopilotAnalyzeStartResponse:
    enforce_copilot_rate_limit(payload, request)
    run = start_after_sales_issue(db, payload)
    background_tasks.add_task(run_after_sales_issue_background, payload, run.run_id)
    return CopilotAnalyzeStartResponse(
        run_id=run.run_id,
        status=run.status,
        events_url=f"/api/runs/{run.run_id}/events",
    )
