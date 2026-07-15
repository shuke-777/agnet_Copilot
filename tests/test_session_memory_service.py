import unittest

from services.redis_service import RedisService, RedisStatus
from services.session_memory_service import SessionMemoryService


class FakeRedisClient:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.set_calls: list[tuple[str, str, int | None]] = []

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.values[key] = value
        self.set_calls.append((key, value, ex))
        return True


class TestSessionMemoryService(unittest.TestCase):
    def setUp(self) -> None:
        self.client = FakeRedisClient()
        self.memory = SessionMemoryService(
            redis_service=RedisService(self.client, RedisStatus("connected", "available")),
            ttl_seconds=1800,
            max_messages=4,
        )

    def test_append_turn_keeps_recent_messages_and_order_id(self) -> None:
        self.memory.append_turn(
            session_id="SESSION-001",
            user_id="USER-001",
            user_message="订单 ORD-1001 还没收到。",
            assistant_message="正在为你查询物流。",
            order_id="ORD-1001",
        )
        self.memory.append_turn(
            session_id="SESSION-001",
            user_id="USER-001",
            user_message="请继续催物流。",
            assistant_message="已创建催物流工单。",
            order_id="ORD-1001",
        )

        context = self.memory.get_context(session_id="SESSION-001", user_id="USER-001")

        self.assertEqual(context.order_id, "ORD-1001")
        self.assertEqual([message.content for message in context.messages], [
            "订单 ORD-1001 还没收到。",
            "正在为你查询物流。",
            "请继续催物流。",
            "已创建催物流工单。",
        ])
        self.assertEqual(self.client.set_calls[-1][2], 1800)

    def test_context_is_not_returned_to_different_user(self) -> None:
        self.memory.append_turn(
            session_id="SESSION-001",
            user_id="USER-001",
            user_message="订单 ORD-1001 还没收到。",
            assistant_message="正在查询。",
            order_id="ORD-1001",
        )

        context = self.memory.get_context(session_id="SESSION-001", user_id="USER-002")

        self.assertEqual(context.messages, [])
        self.assertIsNone(context.order_id)

    def test_unavailable_redis_returns_empty_context_without_raising(self) -> None:
        memory = SessionMemoryService(
            redis_service=RedisService(None, RedisStatus("unavailable", "connection refused")),
        )

        memory.append_turn(
            session_id="SESSION-001",
            user_id="USER-001",
            user_message="订单 ORD-1001 还没收到。",
            assistant_message="正在查询。",
            order_id="ORD-1001",
        )
        context = memory.get_context(session_id="SESSION-001", user_id="USER-001")

        self.assertEqual(context.messages, [])
        self.assertIsNone(context.order_id)
