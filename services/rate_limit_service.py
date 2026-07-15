import os
import time
from dataclasses import dataclass

from services.redis_service import RedisService


DEFAULT_CAPACITY = 10
DEFAULT_WINDOW_SECONDS = 60
TOKEN_BUCKET_SCRIPT = """
local capacity = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local now_ms = tonumber(ARGV[3])

local values = redis.call('HMGET', KEYS[1], 'tokens', 'updated_at')
local tokens = tonumber(values[1])
local updated_at = tonumber(values[2])

if tokens == nil then tokens = capacity end
if updated_at == nil then updated_at = now_ms end

local elapsed_ms = math.max(0, now_ms - updated_at)
tokens = math.min(capacity, tokens + (elapsed_ms * capacity / window_ms))

local allowed = 0
if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
end

redis.call('HSET', KEYS[1], 'tokens', tokens, 'updated_at', now_ms)
redis.call('PEXPIRE', KEYS[1], window_ms)

local retry_after_seconds = 0
if allowed == 0 then
    retry_after_seconds = math.max(1, math.ceil((1 - tokens) * window_ms / capacity / 1000))
end

return {allowed, math.floor(tokens), retry_after_seconds}
"""


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int = 0
    fallback_reason: str | None = None


@dataclass
class CopilotRateLimiter:
    redis_service: RedisService
    capacity: int
    window_seconds: int

    @classmethod
    def from_environment(cls) -> "CopilotRateLimiter":
        return cls(
            redis_service=RedisService.from_environment(),
            capacity=_positive_int_from_environment("COPILOT_RATE_LIMIT_CAPACITY", DEFAULT_CAPACITY),
            window_seconds=_positive_int_from_environment("COPILOT_RATE_LIMIT_WINDOW_SECONDS", DEFAULT_WINDOW_SECONDS),
        )

    def consume(self, subject: str) -> RateLimitResult:
        if self.redis_service.client is None:
            return RateLimitResult(
                allowed=True,
                fallback_reason=f"Redis rate limiting is {self.redis_service.status.status}",
            )

        try:
            result = self.redis_service.client.eval(
                TOKEN_BUCKET_SCRIPT,
                1,
                f"rate_limit:copilot:{subject}",
                self.capacity,
                self.window_seconds * 1000,
                int(time.time() * 1000),
            )
            allowed, _, retry_after_seconds = (int(value) for value in result)
        except Exception as exc:
            return RateLimitResult(allowed=True, fallback_reason=f"Redis rate limiting failed: {exc}")

        if allowed == 1:
            return RateLimitResult(allowed=True)
        return RateLimitResult(allowed=False, retry_after_seconds=max(1, retry_after_seconds))


def _positive_int_from_environment(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default
