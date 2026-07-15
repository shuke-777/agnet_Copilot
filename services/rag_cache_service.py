import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from langchain_core.documents import Document

from schemas.policy import PolicySource
from services.redis_service import RedisService


CacheValue = TypeVar("CacheValue")


@dataclass(frozen=True)
class RagCacheResult(Generic[CacheValue]):
    value: CacheValue
    cache_hit: bool


class RagCache:
    """Optional exact-match cache for stable RAG intermediate results."""

    def __init__(self, *, redis_service: RedisService, ttl_seconds: int = 300) -> None:
        self.redis_service = redis_service
        self.ttl_seconds = ttl_seconds

    @classmethod
    def from_environment(cls) -> "RagCache":
        return cls(
            redis_service=RedisService.from_environment(),
            ttl_seconds=max(1, int(os.getenv("RAG_CACHE_TTL_SECONDS", "300"))),
        )

    def get_or_load_query_rewrite(self, *, user_message: str, intent: str | None, is_abnormal: bool | None, loader: Callable[[], str]) -> RagCacheResult[str]:
        return self._get_or_load(
            operation="query_rewrite", user_message=user_message, intent=intent, is_abnormal=is_abnormal,
            loader=loader,
            deserialize=lambda value: str(json.loads(value)["rewritten_query"]),
            serialize=lambda value: json.dumps({"rewritten_query": value}, ensure_ascii=False),
        )

    def get_or_load_policy_candidates(self, *, user_message: str, intent: str | None, is_abnormal: bool | None, loader: Callable[[], list[Document]]) -> RagCacheResult[list[Document]]:
        return self._get_or_load(
            operation="policy_retrieval", user_message=user_message, intent=intent, is_abnormal=is_abnormal,
            loader=loader,
            deserialize=lambda value: [Document(page_content=item["page_content"], metadata=item["metadata"]) for item in json.loads(value)["candidates"]],
            serialize=lambda value: json.dumps({"candidates": [{"page_content": document.page_content, "metadata": document.metadata} for document in value]}, ensure_ascii=False),
        )

    def get_or_load_policy_rerank(self, *, user_message: str, intent: str | None, is_abnormal: bool | None, loader: Callable[[], list[PolicySource]]) -> RagCacheResult[list[PolicySource]]:
        return self._get_or_load(
            operation="policy_rerank", user_message=user_message, intent=intent, is_abnormal=is_abnormal,
            loader=loader,
            deserialize=lambda value: [PolicySource.model_validate(item) for item in json.loads(value)["policies"]],
            serialize=lambda value: json.dumps({"policies": [policy.model_dump() for policy in value]}, ensure_ascii=False),
        )

    def _get_or_load(self, *, operation: str, user_message: str, intent: str | None, is_abnormal: bool | None, loader: Callable[[], CacheValue], deserialize: Callable[[str], CacheValue], serialize: Callable[[CacheValue], str]) -> RagCacheResult[CacheValue]:
        client = self.redis_service.client
        if client is None:
            return RagCacheResult(value=loader(), cache_hit=False)

        key = self._build_key(operation=operation, user_message=user_message, intent=intent, is_abnormal=is_abnormal)
        try:
            cached_value = client.get(key)
            if cached_value:
                return RagCacheResult(value=deserialize(cached_value), cache_hit=True)
            value = loader()
            client.set(key, serialize(value), ex=self.ttl_seconds)
            return RagCacheResult(value=value, cache_hit=False)
        except Exception:
            return RagCacheResult(value=loader(), cache_hit=False)

    @staticmethod
    def _build_key(*, operation: str, user_message: str, intent: str | None, is_abnormal: bool | None) -> str:
        context = {
            "operation": operation,
            "message_sha256": hashlib.sha256(user_message.encode("utf-8")).hexdigest(),
            "intent": intent or "unknown",
            "is_abnormal": is_abnormal,
            "knowledge_version": os.getenv("RAG_KNOWLEDGE_VERSION", "v1"),
            "rule_version": os.getenv("RAG_RULE_VERSION", "v1"),
            "prompt_version": os.getenv("RAG_QUERY_REWRITE_PROMPT_VERSION", "v1"),
        }
        fingerprint = hashlib.sha256(json.dumps(context, ensure_ascii=True, sort_keys=True).encode("utf-8")).hexdigest()
        return f"rag:exact:{operation}:{fingerprint}"
