print('0707_1')
print('time_stamp:2026_0707')
from dataclasses import dataclass, field
from typing import Any

from langchain_core.documents import Document
from models.agent_trace import AgentStep
from models.business import Logistics, Order
from schemas.copilot import CopilotAnalyzeRequest
from schemas.policy import PolicySource
from services.session_memory_service import SessionContext


@dataclass
class CopilotState:
    payload: CopilotAnalyzeRequest
    run_id: str
    db: Any = None
    session_context: SessionContext = field(default_factory=SessionContext)
    intent: str | None = None
    order_id: str | None = None
    order: Order | None = None
    logistics: Logistics | None = None
    is_abnormal: bool | None = None
    rewritten_query: str | None = None
    policy_candidates: list[Document] = field(default_factory=list)
    retrieved_policies: list[PolicySource] = field(default_factory=list)
    reply_draft: str | None = None
    ticket_id: str | None = None
    ticket_created: bool = False
    ticket_reused: bool = False
    feishu_status: str = "skipped"
    rag_cache: Any = None
    steps: list[AgentStep] = field(default_factory=list)
