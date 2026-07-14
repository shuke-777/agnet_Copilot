import json
import os
import time
from dataclasses import dataclass
from typing import Any, Generic, TypeVar
from urllib.request import Request, urlopen

from pydantic import BaseModel, ValidationError

from services.environment import load_project_environment


T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class LLMCallResult:
    content: dict[str, Any] | None
    provider: str
    model: str | None
    duration_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    fallback_reason: str | None = None

    @property
    def success(self) -> bool:
        return self.content is not None and self.fallback_reason is None


@dataclass(frozen=True)
class StructuredLLMResult(Generic[T]):
    value: T | None
    call: LLMCallResult

    @property
    def success(self) -> bool:
        return self.value is not None and self.call.success


@dataclass(frozen=True)
class LLMGateway:
    provider: str
    base_url: str | None
    api_key: str | None
    model: str | None
    timeout_seconds: float

    @classmethod
    def from_environment(cls) -> "LLMGateway":
        load_project_environment()
        provider = os.getenv("LLM_PROVIDER", "disabled").strip().lower()
        if provider == "disabled":
            return cls(
                provider=provider,
                base_url=None,
                api_key=None,
                model=None,
                timeout_seconds=float(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "10")),
            )

        default_base_url = {
            "openai_compatible": "https://api.openai.com/v1",
            "ollama": "http://127.0.0.1:11434",
        }.get(provider)
        return cls(
            provider=provider,
            base_url=os.getenv("LLM_BASE_URL", default_base_url).rstrip("/") if os.getenv("LLM_BASE_URL", default_base_url) else None,
            api_key=os.getenv("LLM_API_KEY"),
            model=os.getenv("LLM_MODEL"),
            timeout_seconds=float(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "10")),
        )

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> LLMCallResult:
        if self.provider == "disabled":
            return self._failed("LLM provider is disabled")
        if self.provider not in {"openai_compatible", "ollama"}:
            return self._failed(f"Unsupported LLM provider: {self.provider}")
        if not self.model:
            return self._failed("LLM_MODEL is not configured")
        if self.provider == "openai_compatible" and not self.api_key:
            return self._failed("LLM_API_KEY is not configured")

        started_at = time.perf_counter()
        try:
            request = self._build_request(system_prompt=system_prompt, user_prompt=user_prompt)
        except Exception as exc:
            return self._failed(f"LLM request could not be created: {exc}", started_at=started_at)

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return self._failed(f"LLM request failed: {exc}", started_at=started_at)

        try:
            content, input_tokens, output_tokens = self._parse_response(payload)
            return LLMCallResult(
                content=json.loads(content),
                provider=self.provider,
                model=self.model,
                duration_ms=self._duration_ms(started_at),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            return self._failed(f"LLM returned invalid JSON: {exc}", started_at=started_at)

    def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> StructuredLLMResult[T]:
        call = self.complete_json(system_prompt=system_prompt, user_prompt=user_prompt)
        if not call.success or call.content is None:
            return StructuredLLMResult(value=None, call=call)
        try:
            return StructuredLLMResult(value=response_model.model_validate(call.content), call=call)
        except ValidationError as exc:
            return StructuredLLMResult(
                value=None,
                call=LLMCallResult(
                    content=None,
                    provider=call.provider,
                    model=call.model,
                    duration_ms=call.duration_ms,
                    input_tokens=call.input_tokens,
                    output_tokens=call.output_tokens,
                    fallback_reason=f"LLM structured output validation failed: {exc.errors()[0]['msg']}",
                ),
            )

    def _build_request(self, *, system_prompt: str, user_prompt: str) -> Request:
        if self.provider == "openai_compatible":
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0,
            }
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
            url = f"{self.base_url}/chat/completions"
        else:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "format": "json",
                "stream": False,
                "options": {"temperature": 0},
            }
            headers = {"Content-Type": "application/json"}
            url = f"{self.base_url}/api/chat"
        return Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers=headers, method="POST")

    def _parse_response(self, payload: dict[str, Any]) -> tuple[str, int | None, int | None]:
        if self.provider == "openai_compatible":
            usage = payload.get("usage", {})
            return (
                payload["choices"][0]["message"]["content"],
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
            )
        return (
            payload["message"]["content"],
            payload.get("prompt_eval_count"),
            payload.get("eval_count"),
        )

    def _failed(self, reason: str, *, started_at: float | None = None) -> LLMCallResult:
        return LLMCallResult(
            content=None,
            provider=self.provider,
            model=self.model,
            duration_ms=self._duration_ms(started_at),
            fallback_reason=reason,
        )

    @staticmethod
    def _duration_ms(started_at: float | None) -> int:
        if started_at is None:
            return 0
        return int((time.perf_counter() - started_at) * 1000)
