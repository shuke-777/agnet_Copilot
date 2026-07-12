from datetime import datetime
from html import escape

from fastapi import APIRouter, Depends, Form, HTTPException, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from models.agent_trace import AgentRun
from models.business import Logistics, Order, Ticket
from models.database import get_db
from services.dashboard_service import (
    get_agent_performance,
    get_dashboard_overview,
    get_ticket_stats,
)
from services.ticket_transition_service import TicketTransitionError, apply_ticket_transition


router = APIRouter(prefix="/admin", tags=["admin"])


BASE_STYLE = """
<style>
  :root {
    color-scheme: light;
    --bg: #f6f7f9;
    --surface: #ffffff;
    --ink: #1f2933;
    --muted: #667085;
    --line: #d9dee7;
    --accent: #0f766e;
    --accent-soft: #d9f3ef;
    --warn: #b45309;
    --warn-soft: #fff3d6;
    --danger: #b42318;
    --danger-soft: #ffe4e0;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: 14px;
    line-height: 1.5;
  }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }
  .shell { max-width: 1180px; margin: 0 auto; padding: 28px 20px 44px; }
  .topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 20px;
  }
  .brand { display: flex; flex-direction: column; gap: 4px; }
  .eyebrow {
    color: var(--accent);
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0;
    text-transform: uppercase;
  }
  h1 { margin: 0; font-size: 26px; line-height: 1.2; letter-spacing: 0; }
  h2 { margin: 0 0 12px; font-size: 18px; letter-spacing: 0; }
  .nav { display: flex; gap: 10px; flex-wrap: wrap; }
  .nav a {
    border: 1px solid var(--line);
    border-radius: 6px;
    background: var(--surface);
    padding: 7px 10px;
    color: var(--ink);
  }
  .panel {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 16px;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
  }
  .field {
    border-left: 3px solid var(--line);
    padding-left: 10px;
    min-width: 0;
  }
  .label { color: var(--muted); font-size: 12px; margin-bottom: 2px; }
  .value { font-weight: 650; overflow-wrap: anywhere; }
  table { width: 100%; border-collapse: collapse; }
  th, td {
    border-bottom: 1px solid var(--line);
    padding: 10px 8px;
    text-align: left;
    vertical-align: top;
  }
  th { color: var(--muted); font-size: 12px; font-weight: 700; }
  tr:last-child td { border-bottom: 0; }
  .badge {
    display: inline-flex;
    align-items: center;
    min-height: 24px;
    border-radius: 999px;
    padding: 2px 9px;
    background: var(--accent-soft);
    color: var(--accent);
    font-weight: 700;
    font-size: 12px;
    white-space: nowrap;
  }
  .badge.warn { background: var(--warn-soft); color: var(--warn); }
  .badge.danger { background: var(--danger-soft); color: var(--danger); }
  .summary { color: var(--muted); max-width: 36rem; }
  .timeline { display: grid; gap: 10px; }
  .event {
    border-left: 3px solid var(--accent);
    padding: 2px 0 2px 12px;
  }
  .mono {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 12px;
  }
  .empty { color: var(--muted); padding: 12px 0; }
  .filter-form, .action-form { display: flex; align-items: end; flex-wrap: wrap; gap: 10px; }
  .control { display: grid; gap: 4px; color: var(--muted); font-size: 12px; }
  select, input, button {
    min-height: 34px;
    border: 1px solid var(--line);
    border-radius: 6px;
    background: var(--surface);
    color: var(--ink);
    font: inherit;
    padding: 6px 9px;
  }
  button { background: var(--accent); border-color: var(--accent); color: #ffffff; cursor: pointer; }
  button:hover { background: #0a5c56; }
  .action-form { margin-top: 10px; }
  @media (max-width: 760px) {
    .topbar { align-items: flex-start; flex-direction: column; }
    .grid { grid-template-columns: 1fr; }
    table { display: block; overflow-x: auto; }
  }
</style>
"""


def page(title: str, body: str) -> HTMLResponse:
    html = f"""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  {BASE_STYLE}
</head>
<body>
  <main class="shell">
    <div class="topbar">
      <div class="brand">
        <div class="eyebrow">After-sales Copilot</div>
        <h1>{escape(title)}</h1>
      </div>
      <nav class="nav">
        <a href="/admin/dashboard">运营看板</a>
        <a href="/admin/tickets">工单</a>
        <a href="/admin/runs">Agent runs</a>
        <a href="/docs">Swagger</a>
      </nav>
    </div>
    {body}
  </main>
</body>
</html>
"""
    return HTMLResponse(html)


def text(value: object) -> str:
    if value is None:
        return "-"
    return escape(str(value))


def time_text(value: datetime | None) -> str:
    if value is None:
        return "-"
    return escape(value.strftime("%Y-%m-%d %H:%M:%S"))


def status_badge(value: str | None) -> str:
    normalized = value or "-"
    css_class = "badge"
    if normalized in {"high", "failed", "stalled"}:
        css_class += " danger"
    elif normalized in {"todo", "running", "skipped", "processing"}:
        css_class += " warn"
    return f'<span class="{css_class}">{text(normalized)}</span>'


def metric_grid(items: list[tuple[str, object]]) -> str:
    fields = "\n".join(
        f"""
        <div class="field">
          <div class="label">{escape(label)}</div>
          <div class="value">{text(value)}</div>
        </div>
        """
        for label, value in items
    )
    return f'<div class="grid">{fields}</div>'


def percent_text(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value * 100:.1f}%"


def select_option(value: str, label: str, selected_value: str | None) -> str:
    selected = " selected" if value == selected_value else ""
    return f'<option value="{escape(value)}"{selected}>{escape(label)}</option>'


@router.get("", include_in_schema=False)
def admin_home() -> RedirectResponse:
    return RedirectResponse(url="/admin/tickets", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(db: Session = Depends(get_db)) -> HTMLResponse:
    overview = get_dashboard_overview(db)
    ticket_stats = get_ticket_stats(db)
    agent_performance = get_agent_performance(db)

    status_rows = "\n".join(
        f"<tr><td>{text(item.key)}</td><td>{text(item.count)}</td></tr>"
        for item in ticket_stats.status_counts
    ) or '<tr><td colspan="2" class="empty">暂无工单数据。</td></tr>'
    priority_rows = "\n".join(
        f"<tr><td>{text(item.key)}</td><td>{text(item.count)}</td></tr>"
        for item in ticket_stats.priority_counts
    ) or '<tr><td colspan="2" class="empty">暂无工单数据。</td></tr>'
    step_rows = "\n".join(
        f"""
        <tr>
          <td>{text(item.step_name)}</td>
          <td>{text(item.count)}</td>
          <td>{text(item.success_count)}</td>
          <td>{text(item.failed_count)}</td>
          <td>{text(percent_text(item.success_rate))}</td>
          <td>{text(item.average_duration_ms)}</td>
        </tr>
        """
        for item in agent_performance.step_performance
    ) or '<tr><td colspan="6" class="empty">暂无 Agent step 数据。</td></tr>'

    body = f"""
    <section class="panel">
      <h2>运营概览</h2>
      {metric_grid([
          ("工单总数", overview.ticket_total),
          ("待处理工单", overview.pending_ticket_count),
          ("高优先级待处理", overview.high_priority_pending_ticket_count),
          ("Agent Run 总数", overview.agent_run_total),
          ("平均 Run 耗时 ms", overview.average_run_duration_ms),
          ("Agent Run 成功率", percent_text(overview.agent_run_success_rate)),
          ("飞书实际发送次数", overview.feishu_notification_attempt_count),
          ("飞书通知成功率", percent_text(overview.feishu_notification_success_rate)),
      ])}
    </section>
    <section class="panel">
      <h2>工单状态分布</h2>
      <table>
        <thead><tr><th>状态</th><th>数量</th></tr></thead>
        <tbody>{status_rows}</tbody>
      </table>
    </section>
    <section class="panel">
      <h2>工单优先级分布</h2>
      <table>
        <thead><tr><th>优先级</th><th>数量</th></tr></thead>
        <tbody>{priority_rows}</tbody>
      </table>
    </section>
    <section class="panel">
      <h2>Agent Step 性能</h2>
      <table>
        <thead>
          <tr>
            <th>Step</th>
            <th>执行次数</th>
            <th>成功</th>
            <th>失败</th>
            <th>成功率</th>
            <th>平均耗时 ms</th>
          </tr>
        </thead>
        <tbody>{step_rows}</tbody>
      </table>
    </section>
    """
    return page("运营看板", body)


@router.get("/tickets", response_class=HTMLResponse)
def ticket_list_page(
    ticket_status: str | None = Query(default=None, alias="status"),
    priority: str | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    query = select(Ticket).options(selectinload(Ticket.order)).order_by(Ticket.created_at.desc())
    if ticket_status:
        query = query.where(Ticket.status == ticket_status)
    if priority:
        query = query.where(Ticket.priority == priority)
    tickets = list(db.scalars(query))

    if tickets:
        rows = "\n".join(
            f"""
            <tr>
              <td><a class="mono" href="/admin/tickets/{text(ticket.ticket_id)}">{text(ticket.ticket_id)}</a></td>
              <td class="mono">{text(ticket.order_id)}</td>
              <td>{text(ticket.order.product_name if ticket.order else "-")}</td>
              <td>{text(ticket.ticket_type)}</td>
              <td>{status_badge(ticket.priority)}</td>
              <td>{status_badge(ticket.status)}</td>
              <td>{text(ticket.assigned_to)}</td>
              <td class="summary">{text(ticket.summary)}</td>
              <td>{time_text(ticket.created_at)}</td>
              <td>{time_text(ticket.updated_at)}</td>
            </tr>
            """
            for ticket in tickets
        )
    else:
        rows = '<tr><td colspan="10" class="empty">没有符合当前筛选条件的工单。</td></tr>'

    status_options = "".join(
        [select_option("", "全部状态", ticket_status)]
        + [
            select_option(value, value, ticket_status)
            for value in ("todo", "processing", "waiting_user", "waiting_vendor", "resolved", "closed")
        ]
    )
    priority_options = "".join(
        [select_option("", "全部优先级", priority)]
        + [select_option(value, value, priority) for value in ("high", "normal", "low")]
    )

    body = f"""
    <section class="panel">
      <h2>工单筛选</h2>
      <form class="filter-form" method="get" action="/admin/tickets">
        <label class="control">状态<select name="status">{status_options}</select></label>
        <label class="control">优先级<select name="priority">{priority_options}</select></label>
        <button type="submit">筛选</button>
        <a href="/admin/tickets">清除筛选</a>
      </form>
    </section>
    <section class="panel">
      <h2>客服工单</h2>
      <table>
        <thead>
          <tr>
            <th>工单号</th>
            <th>订单号</th>
            <th>商品</th>
            <th>类型</th>
            <th>优先级</th>
            <th>状态</th>
            <th>处理人</th>
            <th>摘要</th>
            <th>创建时间</th>
            <th>更新时间</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </section>
    """
    return page("客服工单", body)


@router.post("/tickets/{ticket_id}/actions/{action}")
def perform_ticket_action(
    ticket_id: str,
    action: str,
    operator: str = Form(min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    try:
        apply_ticket_transition(
            db,
            ticket=ticket,
            action=action,
            operator=operator,
            event_type="manual_status_changed",
            content_prefix="后台人工操作",
        )
    except TicketTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    db.commit()
    return RedirectResponse(url=f"/admin/tickets/{ticket.ticket_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/tickets/{ticket_id}", response_class=HTMLResponse)
def ticket_detail_page(ticket_id: str, db: Session = Depends(get_db)) -> HTMLResponse:
    ticket = db.scalar(
        select(Ticket)
        .options(
            selectinload(Ticket.events),
            selectinload(Ticket.order).selectinload(Order.logistics),
        )
        .where(Ticket.ticket_id == ticket_id)
    )
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    order = ticket.order
    logistics: Logistics | None = order.logistics if order else None
    event_items = "\n".join(
        f"""
        <div class="event">
          <div><strong>{text(event.event_type)}</strong> · {text(event.operator)} · {time_text(event.created_at)}</div>
          <div class="summary">{text(event.content)}</div>
          <div class="mono">{text(event.from_status)} -> {text(event.to_status)}</div>
        </div>
        """
        for event in ticket.events
    )
    if not event_items:
        event_items = '<div class="empty">暂无工单事件。</div>'

    action_labels = {"claim": "接单", "resolve": "解决", "reopen": "重新打开"}
    available_action = {
        "todo": "claim",
        "processing": "resolve",
        "resolved": "reopen",
    }.get(ticket.status)
    action_form = ""
    if available_action:
        action_form = f"""
        <form class="action-form" method="post" action="/admin/tickets/{text(ticket.ticket_id)}/actions/{available_action}">
          <label class="control">操作人<input name="operator" value="人工客服" maxlength="64" required></label>
          <button type="submit">{action_labels[available_action]}</button>
        </form>
        """

    body = f"""
    <section class="panel">
      <h2>工单详情</h2>
      {metric_grid([
          ("工单号", ticket.ticket_id),
          ("订单号", ticket.order_id),
          ("类型", ticket.ticket_type),
          ("状态", ticket.status),
          ("优先级", ticket.priority),
          ("用户", ticket.user_id),
          ("处理人", ticket.assigned_to),
          ("创建来源", ticket.created_by),
      ])}
    </section>
    <section class="panel">
      <h2>处理建议</h2>
      <p><strong>摘要：</strong>{text(ticket.summary)}</p>
      <p><strong>建议动作：</strong>{text(ticket.suggested_action)}</p>
      {action_form}
    </section>
    <section class="panel">
      <h2>订单与物流</h2>
      {metric_grid([
          ("商品", order.product_name if order else None),
          ("订单状态", order.status if order else None),
          ("金额", order.amount if order else None),
          ("承运商", logistics.carrier if logistics else None),
          ("运单号", logistics.tracking_no if logistics else None),
          ("物流状态", logistics.status if logistics else None),
          ("是否异常", "是" if logistics and logistics.is_abnormal else "否"),
          ("最近更新", logistics.last_event_time if logistics else None),
      ])}
      <p class="summary">{text(logistics.last_event if logistics else "未查询到物流信息")}</p>
    </section>
    <section class="panel">
      <h2>工单时间线</h2>
      <div class="timeline">{event_items}</div>
    </section>
    """
    return page("工单详情", body)


@router.get("/runs", response_class=HTMLResponse)
def run_list_page(db: Session = Depends(get_db)) -> HTMLResponse:
    runs = list(db.scalars(select(AgentRun).order_by(AgentRun.created_at.desc()).limit(50)))
    if runs:
        rows = "\n".join(
            f"""
            <tr>
              <td><a class="mono" href="/admin/runs/{text(run.run_id)}">{text(run.run_id)}</a></td>
              <td>{text(run.session_id)}</td>
              <td>{text(run.intent)}</td>
              <td>{status_badge(run.status)}</td>
              <td>{text(run.total_duration_ms)}</td>
              <td class="summary">{text(run.user_message)}</td>
              <td>{time_text(run.created_at)}</td>
            </tr>
            """
            for run in runs
        )
    else:
        rows = '<tr><td colspan="7" class="empty">暂无 Agent run。先调用 Copilot analyze 创建一次执行记录。</td></tr>'

    body = f"""
    <section class="panel">
      <h2>Agent Run</h2>
      <table>
        <thead>
          <tr>
            <th>Run ID</th>
            <th>Session</th>
            <th>意图</th>
            <th>状态</th>
            <th>耗时 ms</th>
            <th>用户问题</th>
            <th>创建时间</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </section>
    """
    return page("Agent Run", body)


@router.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail_page(run_id: str, db: Session = Depends(get_db)) -> HTMLResponse:
    run = db.scalar(
        select(AgentRun)
        .options(selectinload(AgentRun.steps))
        .where(AgentRun.run_id == run_id)
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")

    steps = sorted(run.steps, key=lambda step: step.start_time)
    if steps:
        rows = "\n".join(
            f"""
            <tr>
              <td>{text(step.step_name)}</td>
              <td>{text(step.step_type)}</td>
              <td>{status_badge(step.status)}</td>
              <td>{text(step.duration_ms)}</td>
              <td class="summary">{text(step.input_summary)}</td>
              <td class="summary">{text(step.output_summary)}</td>
              <td class="summary">{text(step.error_message)}</td>
            </tr>
            """
            for step in steps
        )
    else:
        rows = '<tr><td colspan="7" class="empty">暂无 step 记录。</td></tr>'

    body = f"""
    <section class="panel">
      <h2>Agent Run</h2>
      {metric_grid([
          ("Run ID", run.run_id),
          ("Session", run.session_id),
          ("用户", run.user_id),
          ("意图", run.intent),
          ("状态", run.status),
          ("总耗时 ms", run.total_duration_ms),
          ("开始时间", run.created_at),
          ("结束时间", run.finished_at),
      ])}
      <p class="summary"><strong>用户问题：</strong>{text(run.user_message)}</p>
    </section>
    <section class="panel">
      <h2>执行步骤</h2>
      <table>
        <thead>
          <tr>
            <th>Step</th>
            <th>类型</th>
            <th>状态</th>
            <th>耗时 ms</th>
            <th>输入摘要</th>
            <th>输出摘要</th>
            <th>错误</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </section>
    """
    return page("Agent Run", body)
