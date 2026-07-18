from uuid import uuid4

from sqlalchemy.orm import Session

from models.business import Ticket, TicketEvent, utc_now


STATUS_TRANSITIONS = {
    "claim": ("todo", "processing"),
    "resolve": ("processing", "resolved"),
    "reopen": ("resolved", "processing"),
}

APPROVAL_ACTIONS = {
    "approve": ("approved", "processing", "审核通过"),
    "reject": ("rejected", "resolved", "审核拒绝"),
    "manual_confirm": ("pending", "processing", "转人工确认"),
}


class TicketTransitionError(ValueError):
    pass


def apply_ticket_transition(
    db: Session,
    *,
    ticket: Ticket,
    action: str,
    operator: str,
    event_type: str,
    content_prefix: str,
) -> TicketEvent:
    transition = STATUS_TRANSITIONS.get(action)
    if transition is None:
        raise TicketTransitionError(f"unsupported action: {action}")

    expected_from, to_status = transition
    if ticket.status != expected_from:
        raise TicketTransitionError(
            f"cannot transition ticket {ticket.ticket_id} from {ticket.status} with action {action}"
        )

    now = utc_now()
    ticket_event = TicketEvent(
        event_id=f"EVT-{uuid4().hex[:8].upper()}",
        ticket_id=ticket.ticket_id,
        event_type=event_type,
        operator=operator,
        content=f"{content_prefix}：{operator} 执行 {action}",
        from_status=ticket.status,
        to_status=to_status,
        created_at=now,
    )
    ticket.status = to_status
    if action in {"claim", "reopen"}:
        ticket.assigned_to = operator
    ticket.updated_at = now
    db.add(ticket_event)
    return ticket_event


def apply_ticket_approval(
    db: Session,
    *,
    ticket: Ticket,
    action: str,
    operator: str,
    event_type: str,
    content_prefix: str,
) -> TicketEvent:
    approval_action = APPROVAL_ACTIONS.get(action)
    if approval_action is None:
        raise TicketTransitionError(f"unsupported approval action: {action}")
    if not ticket.approval_required:
        raise TicketTransitionError(f"ticket {ticket.ticket_id} does not require approval")
    if ticket.approval_status != "pending":
        raise TicketTransitionError(
            f"cannot approve ticket {ticket.ticket_id} from approval status {ticket.approval_status}"
        )

    to_approval_status, to_ticket_status, label = approval_action
    now = utc_now()
    ticket_event = TicketEvent(
        event_id=f"EVT-{uuid4().hex[:8].upper()}",
        ticket_id=ticket.ticket_id,
        event_type=event_type,
        operator=operator,
        content=f"{content_prefix}：{operator} 执行 {label}",
        from_status=ticket.approval_status,
        to_status=to_approval_status,
        created_at=now,
    )
    ticket.approval_status = to_approval_status
    ticket.approval_decided_by = operator
    ticket.approval_decided_at = now
    ticket.status = to_ticket_status
    ticket.assigned_to = operator
    ticket.updated_at = now
    db.add(ticket_event)
    return ticket_event
