print('0707_1')
print('time_stamp:2026_0707')
from dataclasses import dataclass, field
from typing import Any

from models.agent_trace import AgentStep
from models.business import Logistics, Order
from schemas.copilot import CopilotAnalyzeRequest
from schemas.policy import PolicySource


@dataclass
class CopilotState:
    payload: CopilotAnalyzeRequest
    run_id: str
    db: Any = None
    intent: str | None = None
    order_id: str | None = None
    order: Order | None = None
    logistics: Logistics | None = None
    is_abnormal: bool | None = None
    retrieved_policies: list[PolicySource] = field(default_factory=list)
    reply_draft: str | None = None
    ticket_id: str | None = None
    feishu_status: str = "skipped"
    steps: list[AgentStep] = field(default_factory=list)
