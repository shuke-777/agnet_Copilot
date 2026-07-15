import sys
import unittest
from pathlib import Path

from langchain_core.documents import Document
from schemas.policy import PolicySource
from services.redis_service import RedisService, RedisStatus


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class FakeRedisClient:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.values[key] = value
        return True


class TestRagCache(unittest.TestCase):
    def setUp(self) -> None:
        from services.rag_cache_service import RagCache

        self.cache = RagCache(
            redis_service=RedisService(FakeRedisClient(), RedisStatus("connected", "available")),
            ttl_seconds=300,
        )

    def test_query_rewrite_cache_reuses_value_for_same_rag_context(self) -> None:
        first = self.cache.get_or_load_query_rewrite(
            user_message="订单 ORD-1001 怎么还没收到？",
            intent="logistics_delay",
            is_abnormal=True,
            loader=lambda: "改写后的物流异常检索词",
        )
        second = self.cache.get_or_load_query_rewrite(
            user_message="订单 ORD-1001 怎么还没收到？",
            intent="logistics_delay",
            is_abnormal=True,
            loader=lambda: "不应执行",
        )

        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)
        self.assertEqual(second.value, "改写后的物流异常检索词")

    def test_context_change_uses_different_rag_cache_key(self) -> None:
        self.cache.get_or_load_policy_candidates(
            user_message="订单 ORD-1001 怎么还没收到？",
            intent="logistics_delay",
            is_abnormal=True,
            loader=lambda: [Document(page_content="异常物流 SOP", metadata={"source_id": "abnormal"})],
        )
        changed_context = self.cache.get_or_load_policy_candidates(
            user_message="订单 ORD-1001 怎么还没收到？",
            intent="logistics_delay",
            is_abnormal=False,
            loader=lambda: [Document(page_content="正常物流话术", metadata={"source_id": "normal"})],
        )

        self.assertFalse(changed_context.cache_hit)
        self.assertEqual(changed_context.value[0].page_content, "正常物流话术")

    def test_unavailable_redis_executes_loader_without_cache_hit(self) -> None:
        from services.rag_cache_service import RagCache

        cache = RagCache(
            redis_service=RedisService(None, RedisStatus("unavailable", "connection refused")),
            ttl_seconds=300,
        )
        result = cache.get_or_load_policy_rerank(
            user_message="订单 ORD-1001 怎么还没收到？",
            intent="logistics_delay",
            is_abnormal=True,
            loader=lambda: [PolicySource(source_id="source", title="物流异常 SOP", content="内容", score=1.0)],
        )

        self.assertFalse(result.cache_hit)
        self.assertEqual(result.value[0].source_id, "source")
