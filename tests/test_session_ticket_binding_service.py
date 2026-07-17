import unittest
from datetime import datetime

from models.business import SessionTicketBinding, Ticket
from models.database import SessionLocal
from services.session_ticket_binding_service import (
    ANONYMOUS_USER_SCOPE,
    SessionBindingDataError,
    SessionOrderMismatchError,
    SessionTicketBindingService,
)


class TestSessionTicketBindingService(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.service = SessionTicketBindingService(self.db)
        self.ticket = self._make_ticket("TCK-BINDING-001")

    def tearDown(self) -> None:
        self.db.close()

    def _make_ticket(
        self,
        ticket_id: str,
        *,
        order_id: str = "ORD-1001",
        status: str = "todo",
    ) -> Ticket:
        ticket = Ticket(
            ticket_id=ticket_id,
            ticket_type="logistics_delay",
            priority="high",
            status=status,
            user_id="USER-001",
            order_id=order_id,
            summary="测试会话主工单绑定",
            suggested_action="联系承运商核实。",
            created_by="agent",
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    def test_bind_ticket_creates_stable_anonymous_binding(self) -> None:
        binding = self.service.bind_ticket(
            session_id="SESSION-ANON",
            user_id=None,
            order_id="ORD-1001",
            ticket_id=self.ticket.ticket_id,
        )

        persisted = self.service.get_binding(session_id="SESSION-ANON", user_id=None)
        self.assertEqual(binding.user_scope, ANONYMOUS_USER_SCOPE)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.ticket_id, self.ticket.ticket_id)

    def test_get_binding_isolated_by_user_scope(self) -> None:
        self.service.bind_ticket(
            session_id="SESSION-SHARED",
            user_id="USER-001",
            order_id="ORD-1001",
            ticket_id=self.ticket.ticket_id,
        )

        self.assertIsNone(
            self.service.get_binding(session_id="SESSION-SHARED", user_id="USER-002")
        )

    def test_bind_ticket_updates_ticket_for_same_order(self) -> None:
        original = self.service.bind_ticket(
            session_id="SESSION-UPDATE",
            user_id="USER-001",
            order_id="ORD-1001",
            ticket_id=self.ticket.ticket_id,
        )
        original_created_at = original.created_at
        replacement = self._make_ticket("TCK-BINDING-002")

        updated = self.service.bind_ticket(
            session_id="SESSION-UPDATE",
            user_id="USER-001",
            order_id="ORD-1001",
            ticket_id=replacement.ticket_id,
        )

        self.assertEqual(updated.created_at, original_created_at)
        self.assertEqual(updated.ticket_id, replacement.ticket_id)
        self.assertGreaterEqual(updated.updated_at, original_created_at)

    def test_bind_ticket_rejects_different_order_for_same_scope(self) -> None:
        self.service.bind_ticket(
            session_id="SESSION-CONFLICT",
            user_id="USER-001",
            order_id="ORD-1001",
            ticket_id=self.ticket.ticket_id,
        )
        other_ticket = self._make_ticket(
            "TCK-BINDING-003",
            order_id="ORD-1002",
        )

        with self.assertRaises(SessionOrderMismatchError) as raised:
            self.service.bind_ticket(
                session_id="SESSION-CONFLICT",
                user_id="USER-001",
                order_id="ORD-1002",
                ticket_id=other_ticket.ticket_id,
            )

        self.assertEqual(raised.exception.bound_order_id, "ORD-1001")
        self.assertEqual(raised.exception.requested_order_id, "ORD-1002")
        binding = self.service.get_binding(
            session_id="SESSION-CONFLICT",
            user_id="USER-001",
        )
        self.assertEqual(binding.ticket_id, self.ticket.ticket_id)

    def test_get_active_ticket_ignores_resolved_ticket(self) -> None:
        self.ticket.status = "resolved"
        self.db.commit()
        self.service.bind_ticket(
            session_id="SESSION-RESOLVED",
            user_id="USER-001",
            order_id="ORD-1001",
            ticket_id=self.ticket.ticket_id,
        )

        self.assertIsNone(
            self.service.get_active_ticket(
                session_id="SESSION-RESOLVED",
                user_id="USER-001",
            )
        )

    def test_get_active_ticket_rejects_missing_bound_ticket(self) -> None:
        self.db.add(
            SessionTicketBinding(
                binding_id="STB-MISSING",
                session_id="SESSION-MISSING",
                user_scope="USER-001",
                order_id="ORD-1001",
                ticket_id="TCK-MISSING",
                created_at=datetime(2026, 7, 17, 12, 0, 0),
                updated_at=datetime(2026, 7, 17, 12, 0, 0),
            )
        )
        self.db.commit()

        with self.assertRaises(SessionBindingDataError):
            self.service.get_active_ticket(
                session_id="SESSION-MISSING",
                user_id="USER-001",
            )


if __name__ == "__main__":
    unittest.main()
