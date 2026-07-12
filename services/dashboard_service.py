from collections import Counter, defaultdict
from statistics import fmean

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.agent_trace import AgentRun, AgentStep
from models.business import Ticket
from schemas.dashboard import (
    AgentPerformance,
    DashboardOverview,
    MetricCount,
    StepPerformance,
    TicketStats,
)


PENDING_TICKET_STATUSES = {"todo", "processing", "waiting_user", "waiting_vendor"}


def calculate_rate(success_count: int, total_count: int) -> float | None:
    if total_count == 0:
        return None
    return round(success_count / total_count, 4)


def calculate_average(values: list[int]) -> float | None:
    if not values:
        return None
    return round(fmean(values), 2)


def load_dashboard_records(db: Session) -> tuple[list[Ticket], list[AgentRun], list[AgentStep]]:
    tickets = list(db.scalars(select(Ticket)))
    runs = list(db.scalars(select(AgentRun)))
    steps = list(db.scalars(select(AgentStep)))
    return tickets, runs, steps


def build_ticket_stats(tickets: list[Ticket]) -> TicketStats:
    status_counts = Counter(ticket.status for ticket in tickets)
    priority_counts = Counter(ticket.priority for ticket in tickets)
    return TicketStats(
        status_counts=[MetricCount(key=key, count=count) for key, count in sorted(status_counts.items())],
        priority_counts=[MetricCount(key=key, count=count) for key, count in sorted(priority_counts.items())],
    )


def build_agent_performance(runs: list[AgentRun], steps: list[AgentStep]) -> AgentPerformance:
    success_count = sum(run.status == "success" for run in runs)
    durations = [run.total_duration_ms for run in runs if run.total_duration_ms is not None]
    grouped_steps: dict[str, list[AgentStep]] = defaultdict(list)
    for step in steps:
        grouped_steps[step.step_name].append(step)

    step_performance = []
    for step_name, step_group in sorted(grouped_steps.items()):
        completed_durations = [step.duration_ms for step in step_group if step.duration_ms is not None]
        successful_steps = sum(step.status == "success" for step in step_group)
        failed_steps = sum(step.status == "failed" for step in step_group)
        step_performance.append(
            StepPerformance(
                step_name=step_name,
                count=len(step_group),
                success_count=successful_steps,
                failed_count=failed_steps,
                success_rate=calculate_rate(successful_steps, len(step_group)),
                average_duration_ms=calculate_average(completed_durations),
            )
        )

    return AgentPerformance(
        agent_run_total=len(runs),
        average_run_duration_ms=calculate_average(durations),
        agent_run_success_rate=calculate_rate(success_count, len(runs)),
        step_performance=step_performance,
    )


def get_dashboard_overview(db: Session) -> DashboardOverview:
    tickets, runs, steps = load_dashboard_records(db)
    agent_performance = build_agent_performance(runs, steps)
    pending_tickets = [ticket for ticket in tickets if ticket.status in PENDING_TICKET_STATUSES]
    attempted_feishu_steps = [
        step for step in steps if step.step_name == "feishu_notify" and step.status in {"success", "failed"}
    ]
    feishu_success_count = sum(step.status == "success" for step in attempted_feishu_steps)

    return DashboardOverview(
        ticket_total=len(tickets),
        pending_ticket_count=len(pending_tickets),
        high_priority_pending_ticket_count=sum(ticket.priority == "high" for ticket in pending_tickets),
        agent_run_total=agent_performance.agent_run_total,
        average_run_duration_ms=agent_performance.average_run_duration_ms,
        agent_run_success_rate=agent_performance.agent_run_success_rate,
        feishu_notification_attempt_count=len(attempted_feishu_steps),
        feishu_notification_success_rate=calculate_rate(feishu_success_count, len(attempted_feishu_steps)),
    )


def get_ticket_stats(db: Session) -> TicketStats:
    tickets, _, _ = load_dashboard_records(db)
    return build_ticket_stats(tickets)


def get_agent_performance(db: Session) -> AgentPerformance:
    _, runs, steps = load_dashboard_records(db)
    return build_agent_performance(runs, steps)
