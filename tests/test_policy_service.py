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

    def test_retrieves_signed_delivery_dispute_sop(self) -> None:
        policies = retrieve_after_sales_policies(
            query="物流显示签收，但是用户说订单未收到，可能是前台代收。",
            is_abnormal=False,
            limit=4,
        )

        source_ids = {policy.source_id for policy in policies}
        self.assertIn("delivery_dispute_signed_sop", source_ids)

    def test_retrieves_high_value_refund_approval_rule(self) -> None:
        policies = retrieve_after_sales_policies(
            query="高金额订单申请退款，需要人工审核。",
            intent="refund",
            is_abnormal=False,
            limit=4,
        )

        source_ids = {policy.source_id for policy in policies}
        self.assertIn("high_value_refund_approval_rule", source_ids)

    def test_retrieves_exchange_address_cancel_and_compensation_rules(self) -> None:
        scenarios = {
            "用户想换货，需要确认库存和重发流程。": ("exchange", "exchange_processing_rule"),
            "订单发货后用户要求改地址。": ("address_change", "address_change_risk_rule"),
            "用户想取消订单，需要审核交易状态。": ("cancel_order", "order_cancel_approval_rule"),
            "用户要求补偿和赔付，需要人工确认。": ("compensation", "compensation_approval_rule"),
        }

        for query, (intent, source_id) in scenarios.items():
            with self.subTest(source_id=source_id):
                policies = retrieve_after_sales_policies(
                    query=query,
                    intent=intent,
                    is_abnormal=None,
                    limit=5,
                )
                source_ids = {policy.source_id for policy in policies}
                self.assertIn(source_id, source_ids)
