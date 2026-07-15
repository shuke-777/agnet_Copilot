from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from models.database import get_db
from schemas.copilot import CopilotAnalyzeRequest, CopilotAnalyzeResponse
from services.copilot_service import analyze_after_sales_issue
from services.rate_limit_service import CopilotRateLimiter


router = APIRouter(prefix="/api/copilot", tags=["copilot"])


@router.post("/analyze", response_model=CopilotAnalyzeResponse)
def analyze_copilot_message(
    payload: CopilotAnalyzeRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> CopilotAnalyzeResponse:
    subject = payload.user_id or f"ip:{request.client.host if request.client else 'unknown'}"
    rate_limit = CopilotRateLimiter.from_environment().consume(subject)
    if not rate_limit.allowed:
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
    return analyze_after_sales_issue(db, payload)
