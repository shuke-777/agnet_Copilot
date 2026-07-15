import os
from dataclasses import dataclass
from typing import Any, Callable

from services.environment import load_project_environment


RedisClientFactory = Callable[..., Any]


@dataclass(frozen=True)
class RedisStatus:
    status: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"status": self.status, "detail": self.detail}


@dataclass
class RedisService:
    client: Any | None
    status: RedisStatus

    @classmethod
    def from_environment(
        cls,
        *,
        client_factory: RedisClientFactory | None = None,
    ) -> "RedisService":
        """Create an optional Redis connection without blocking local development."""
        load_project_environment()
        redis_url = os.getenv("REDIS_URL", "").strip()
        if not redis_url:
            return cls(
                client=None,
                status=RedisStatus("disabled", "REDIS_URL is not configured"),
            )

        try:
            if client_factory is None:
                from redis import Redis

                client_factory = Redis.from_url
            timeout_seconds = float(os.getenv("REDIS_CONNECT_TIMEOUT_SECONDS", "1"))
            client = client_factory(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=timeout_seconds,
                socket_timeout=timeout_seconds,
            )
            client.ping()
        except Exception as exc:
            return cls(
                client=None,
                status=RedisStatus("unavailable", f"Redis connection failed: {exc}"),
            )

        return cls(
            client=client,
            status=RedisStatus("connected", "Redis connection is available"),
        )
