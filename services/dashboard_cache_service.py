import os
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel

from schemas.dashboard import AgentPerformance, DashboardOverview, TicketStats
from services.redis_service import RedisService


DashboardValue = TypeVar("DashboardValue", bound=BaseModel)


class DashboardCache:
    """Optional Redis cache for the three dashboard aggregation responses."""

    OVERVIEW_KEY = "dashboard:overview"
    TICKET_STATS_KEY = "dashboard:ticket-stats"
    AGENT_PERFORMANCE_KEY = "dashboard:agent-performance"
    KEYS = (OVERVIEW_KEY, TICKET_STATS_KEY, AGENT_PERFORMANCE_KEY)

    def __init__(self, *, redis_service: RedisService, ttl_seconds: int = 60) -> None:
        self.redis_service = redis_service
        self.ttl_seconds = ttl_seconds

    @classmethod
    def from_environment(cls) -> "DashboardCache":
        ttl_seconds = max(1, int(os.getenv("DASHBOARD_CACHE_TTL_SECONDS", "60")))
        return cls(redis_service=RedisService.from_environment(), ttl_seconds=ttl_seconds)

    def get_or_load_overview(self, loader: Callable[[], DashboardOverview]) -> DashboardOverview:
        return self._get_or_load(self.OVERVIEW_KEY, DashboardOverview, loader)

    def get_or_load_ticket_stats(self, loader: Callable[[], TicketStats]) -> TicketStats:
        return self._get_or_load(self.TICKET_STATS_KEY, TicketStats, loader)

    def get_or_load_agent_performance(self, loader: Callable[[], AgentPerformance]) -> AgentPerformance:
        return self._get_or_load(self.AGENT_PERFORMANCE_KEY, AgentPerformance, loader)

    def _get_or_load(
        self,
        key: str,
        response_model: type[DashboardValue],
        loader: Callable[[], DashboardValue],
    ) -> DashboardValue:
        client = self.redis_service.client
        if client is None:
            return loader()

        try:
            cached_value = client.get(key)
            if cached_value:
                return response_model.model_validate_json(cached_value)

            value = loader()
            client.set(key, value.model_dump_json(), ex=self.ttl_seconds)
            return value
        except Exception:
            return loader()

    def invalidate(self) -> None:
        client = self.redis_service.client
        if client is None:
            return
        try:
            client.delete(*self.KEYS)
        except Exception:
            return


def invalidate_dashboard_cache() -> None:
    """Best-effort invalidation after persisted business data changes."""
    DashboardCache.from_environment().invalidate()
