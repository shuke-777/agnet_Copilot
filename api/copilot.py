from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from models.database import get_db
from schemas.copilot import CopilotAnalyzeRequest, CopilotAnalyzeResponse
from services.copilot_service import analyze_after_sales_issue


router = APIRouter(prefix="/api/copilot", tags=["copilot"])


@router.post("/analyze", response_model=CopilotAnalyzeResponse)
def analyze_copilot_message(
    payload: CopilotAnalyzeRequest,
    db: Session = Depends(get_db),
) -> CopilotAnalyzeResponse:
    return analyze_after_sales_issue(db, payload)
