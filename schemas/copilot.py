from typing import Literal

from pydantic import BaseModel, Field

from schemas.policy import PolicySource


class CopilotHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class CopilotAnalyzeRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    user_id: str | None = Field(default=None, max_length=64)
    user_message: str = Field(min_length=1)
    history: list[CopilotHistoryMessage] = Field(default_factory=list, max_length=10)


class CopilotAnalyzeResponse(BaseModel):
    run_id: str
    intent: str
    order_id: str
    is_abnormal: bool
    reply_draft: str
    ticket_created: bool
    ticket_reused: bool
    ticket_association: Literal["created", "reused", "session_linked", "none"]
    ticket_id: str | None
    feishu_status: str
    policy_sources: list[PolicySource] = Field(default_factory=list)
