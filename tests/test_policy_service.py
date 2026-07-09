import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.policy_service import retrieve_after_sales_policies


class TestPolicyService(unittest.TestCase):
    def test_retrieves_abnormal_logistics_sop(self) -> None:
        policies = retrieve_after_sales_policies(
            query="订单没收到，物流超过 72 小时未更新，需要催物流。",
            is_abnormal=True,
        )

        self.assertGreaterEqual(len(policies), 1)
        self.assertEqual(policies[0].source_id, "logistics_delay_72h_sop")
        self.assertIn("物流超过 72 小时未更新处理 SOP", policies[0].title)

    def test_retrieves_normal_logistics_script(self) -> None:
        policies = retrieve_after_sales_policies(
            query="用户咨询订单物流，物流状态正常。",
            is_abnormal=False,
        )

        source_ids = {policy.source_id for policy in policies}
        self.assertIn("normal_logistics_reply_script", source_ids)

    def test_retrieval_can_return_empty_list_for_unrelated_query(self) -> None:
        policies = retrieve_after_sales_policies(
            query="会员积分兑换规则",
            is_abnormal=None,
            score_threshold=0.95,
        )

        self.assertEqual(policies, [])
