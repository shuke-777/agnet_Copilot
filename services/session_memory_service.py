import json
import os
from dataclasses import dataclass, field

from schemas.copilot import CopilotHistoryMessage
from services.redis_service import RedisService


@dataclass(frozen=True)
class SessionContext:
    messages: list[CopilotHistoryMessage] = field(default_factory=list)
    order_id: str | None = None


class SessionMemoryService:
    """Optional short-term Copilot context stored per session and user."""

    def __init__(
        self,
        *,
        redis_service: RedisService,
        ttl_seconds: int = 1800,
        max_messages: int = 10,
    ) -> None:
        self.redis_service = redis_service
        self.ttl_seconds = ttl_seconds
        self.max_messages = max_messages

    @classmethod
    def from_environment(cls) -> "SessionMemoryService":
        return cls(
            redis_service=RedisService.from_environment(),
            ttl_seconds=max(1, int(os.getenv("SESSION_CONTEXT_TTL_SECONDS", "1800"))),
            max_messages=max(1, int(os.getenv("SESSION_CONTEXT_MAX_MESSAGES", "10"))),
        )

    def get_context(self, *, session_id: str, user_id: str | None) -> SessionContext:
        client = self.redis_service.client
        if client is None:
            return SessionContext()

        try:
            raw_context = client.get(self._key(session_id))
            if not raw_context:
                return SessionContext()
            payload = json.loads(raw_context)
            if payload.get("user_id") != user_id:
                return SessionContext()
            messages = [CopilotHistoryMessage.model_validate(item) for item in payload.get("messages", [])]
            return SessionContext(messages=messages[-self.max_messages :], order_id=payload.get("order_id"))
        except Exception:
            return SessionContext()

    def append_turn(
        self,
        *,
        session_id: str,
        user_id: str | None,
        user_message: str,
        assistant_message: str,
        order_id: str | None,
    ) -> None:
        client = self.redis_service.client
        if client is None:
            return

        existing = self.get_context(session_id=session_id, user_id=user_id)
        messages = [
            *existing.messages,
            CopilotHistoryMessage(role="user", content=user_message),
            CopilotHistoryMessage(role="assistant", content=assistant_message),
        ][-self.max_messages :]
        payload = {
            "user_id": user_id,
            "order_id": order_id or existing.order_id,
            "messages": [message.model_dump() for message in messages],
        }
        try:
            client.set(self._key(session_id), json.dumps(payload, ensure_ascii=False), ex=self.ttl_seconds)
        except Exception:
            return

    @staticmethod
    def _key(session_id: str) -> str:
        return f"session_context:copilot:{session_id}"
