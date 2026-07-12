import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.policy_service import (
    rerank_after_sales_policies,
    retrieve_policy_candidates,
    rewrite_after_sales_query,
)


class TestRagM6(unittest.TestCase):
    def test_query_rewrite_adds_refund_context(self) -> None:
        rewritten_query = rewrite_after_sales_query(
            "订单 ORD-1002 可以退钱吗？",
            intent="refund",
            is_abnormal=False,
        )

        self.assertIn("订单 ORD-1002 可以退钱吗？", rewritten_query)
        self.assertIn("退款", rewritten_query)
        self.assertIn("售后规则", rewritten_query)

    def test_rerank_returns_refund_policy_for_refund_intent(self) -> None:
        query = rewrite_after_sales_query(
            "订单 ORD-1002 可以退钱吗？",
            intent="refund",
            is_abnormal=False,
        )
        policies = rerank_after_sales_policies(
            query=query,
            candidates=retrieve_policy_candidates(query),
            intent="refund",
            is_abnormal=False,
        )

        self.assertGreaterEqual(len(policies), 1)
        self.assertEqual(policies[0].source_id, "refund_processing_rule")

    def test_rerank_returns_return_policy_for_return_intent(self) -> None:
        query = rewrite_after_sales_query(
            "订单 ORD-1002 想退货怎么办？",
            intent="return",
            is_abnormal=False,
        )
        policies = rerank_after_sales_policies(
            query=query,
            candidates=retrieve_policy_candidates(query),
            intent="return",
            is_abnormal=False,
        )

        self.assertGreaterEqual(len(policies), 1)
        self.assertEqual(policies[0].source_id, "return_application_rule")
