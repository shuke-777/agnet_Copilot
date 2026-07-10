from datetime import datetime
from html import escape

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from models.agent_trace import AgentRun
from models.business import Logistics, Order, Ticket
from models.database import get_db


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


@router.get("", include_in_schema=False)
def admin_home() -> RedirectResponse:
    return RedirectResponse(url="/admin/tickets", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/tickets", response_class=HTMLResponse)
def ticket_list_page(db: Session = Depends(get_db)) -> HTMLResponse:
    tickets = list(
        db.scalars(
            select(Ticket)
            .options(selectinload(Ticket.order))
            .order_by(Ticket.created_at.desc())
        )
    )

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
              <td class="summary">{text(ticket.summary)}</td>
              <td>{time_text(ticket.created_at)}</td>
            </tr>
            """
            for ticket in tickets
        )
    else:
        rows = '<tr><td colspan="8" class="empty">暂无工单。先调用 Copilot analyze 创建一条异常物流工单。</td></tr>'

    body = f"""
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
            <th>摘要</th>
            <th>创建时间</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </section>
    """
    return page("客服工单", body)


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
