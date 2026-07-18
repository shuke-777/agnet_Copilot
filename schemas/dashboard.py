from pydantic import BaseModel, Field


class MetricCount(BaseModel):
    key: str
    count: int


class DashboardOverview(BaseModel):
    ticket_total: int
    pending_ticket_count: int
    high_priority_pending_ticket_count: int
    agent_run_total: int
    average_run_duration_ms: float | None
    agent_run_success_rate: float | None
    feishu_notification_attempt_count: int
    feishu_notification_success_rate: float | None


class TicketStats(BaseModel):
    status_counts: list[MetricCount] = Field(default_factory=list)
    priority_counts: list[MetricCount] = Field(default_factory=list)


class StepPerformance(BaseModel):
    step_name: str
    count: int
    success_count: int
    failed_count: int
    success_rate: float | None
    average_duration_ms: float | None


class AgentPerformance(BaseModel):
    agent_run_total: int
    average_run_duration_ms: float | None
    agent_run_success_rate: float | None
    step_performance: list[StepPerformance] = Field(default_factory=list)


class RiskRankingItem(BaseModel):
    key: str
    score: float
    count: int


class RiskRanking(BaseModel):
    source: str
    carrier_risks: list[RiskRankingItem] = Field(default_factory=list)
    high_priority_tickets: list[RiskRankingItem] = Field(default_factory=list)
    frequent_issue_risks: list[RiskRankingItem] = Field(default_factory=list)
