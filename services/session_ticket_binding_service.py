from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.business import SessionTicketBinding, Ticket, utc_now


ANONYMOUS_USER_SCOPE = "__anonymous__"
ACTIVE_TICKET_STATUSES = ("todo", "processing")


class SessionOrderMismatchError(ValueError):
    def __init__(self, *, bound_order_id: str, requested_order_id: str) -> None:
        super().__init__(
            f"session is bound to {bound_order_id}, not {requested_order_id}"
        )
        self.bound_order_id = bound_order_id
        self.requested_order_id = requested_order_id


class SessionBindingDataError(ValueError):
    pass


class SessionTicketBindingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def normalize_user_scope(user_id: str | None) -> str:
        return user_id or ANONYMOUS_USER_SCOPE

    def get_binding(
        self,
        *,
        session_id: str,
        user_id: str | None,
    ) -> SessionTicketBinding | None:
        return self.db.query(SessionTicketBinding).filter_by(
            session_id=session_id,
            user_scope=self.normalize_user_scope(user_id),
        ).one_or_none()

    def get_active_ticket(
        self,
        *,
        session_id: str,
        user_id: str | None,
    ) -> Ticket | None:
        binding = self.get_binding(session_id=session_id, user_id=user_id)
        if binding is None:
            return None

        ticket = self.db.get(Ticket, binding.ticket_id)
        if ticket is None or ticket.order_id != binding.order_id:
            raise SessionBindingDataError(
                f"binding {binding.binding_id} points to an invalid ticket"
            )
        if ticket.status not in ACTIVE_TICKET_STATUSES:
            return None
        return ticket

    def bind_ticket(
        self,
        *,
        session_id: str,
        user_id: str | None,
        order_id: str,
        ticket_id: str,
    ) -> SessionTicketBinding:
        binding = self.get_binding(session_id=session_id, user_id=user_id)
        if binding is not None:
            return self._update_binding(
                binding,
                order_id=order_id,
                ticket_id=ticket_id,
            )

        binding = SessionTicketBinding(
            binding_id=f"STB-{uuid4().hex[:8].upper()}",
            session_id=session_id,
            user_scope=self.normalize_user_scope(user_id),
            order_id=order_id,
            ticket_id=ticket_id,
        )
        try:
            with self.db.begin_nested():
                self.db.add(binding)
                self.db.flush()
        except IntegrityError:
            binding = self.get_binding(session_id=session_id, user_id=user_id)
            if binding is None:
                raise
            return self._update_binding(
                binding,
                order_id=order_id,
                ticket_id=ticket_id,
            )
        return binding

    def _update_binding(
        self,
        binding: SessionTicketBinding,
        *,
        order_id: str,
        ticket_id: str,
    ) -> SessionTicketBinding:
        if binding.order_id != order_id:
            raise SessionOrderMismatchError(
                bound_order_id=binding.order_id,
                requested_order_id=order_id,
            )
        if binding.ticket_id != ticket_id:
            binding.ticket_id = ticket_id
            binding.updated_at = utc_now()
            self.db.flush()
        return binding
