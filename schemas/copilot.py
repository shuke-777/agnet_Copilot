from pydantic import BaseModel, Field


class CopilotAnalyzeRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    user_id: str | None = Field(default=None, max_length=64)
    user_message: str = Field(min_length=1)


class CopilotAnalyzeResponse(BaseModel):
    run_id: str
    intent: str
    order_id: str
    is_abnormal: bool
    reply_draft: str
    ticket_created: bool
    ticket_id: str | None
