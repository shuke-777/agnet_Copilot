from langchain_core.documents import Document


POLICY_DOCUMENTS = [
    Document(
        page_content=(
            "物流超过 72 小时未更新处理 SOP：若订单已发货但物流超过 72 小时未更新，"
            "客服应创建催物流工单，联系承运商核实卡点，并向用户同步预计处理时效。"
        ),
        metadata={
            "source_id": "logistics_delay_72h_sop",
            "title": "物流超过 72 小时未更新处理 SOP",
            "scenario": "abnormal_logistics",
        },
    ),
    Document(
        page_content=(
            "物流正常但用户催单话术：若物流仍在正常运输或已签收，应向用户说明当前物流状态，"
            "提供最新物流节点，并告知如后续长时间未更新可继续联系客服。"
        ),
        metadata={
            "source_id": "normal_logistics_reply_script",
            "title": "物流正常查询与催单回复话术",
            "scenario": "normal_logistics",
        },
    ),
    Document(
        page_content=(
            "催物流工单创建标准：当出现物流停滞、疑似丢件、超过承诺时效未送达等情况时，"
            "工单类型应标记为 logistics_delay，优先级可设为 high。"
        ),
        metadata={
            "source_id": "logistics_ticket_creation_standard",
            "title": "催物流工单创建标准",
            "scenario": "abnormal_logistics",
        },
    ),
    Document(
        page_content=(
            "客服安抚回复规范：回复需先说明已查询订单与物流，再给出处理动作；"
            "对异常物流应表达会继续跟进，不承诺无法保证的具体送达时间。"
        ),
        metadata={
            "source_id": "customer_reassurance_reply_guideline",
            "title": "客服安抚回复规范",
            "scenario": "general_reply",
        },
    ),
    Document(
        page_content=(
            "发货时效规则：订单支付成功后应在承诺发货时效内安排发货。"
            "若超过承诺时效仍未发货，客服应核实订单状态并向用户说明预计发货时间，"
            "不得承诺未经仓库确认的具体日期。"
        ),
        metadata={
            "source_id": "shipping_timeliness_rule",
            "title": "发货时效与未发货处理规则",
            "scenario": "shipping_timeliness",
        },
    ),
    Document(
        page_content=(
            "退款处理规则：客服应先核实订单支付、发货和售后申请状态，再向用户说明退款条件、"
            "处理方式和预计到账时效。未完成审核前，不得承诺退款一定成功。"
        ),
        metadata={
            "source_id": "refund_processing_rule",
            "title": "退款咨询处理规则",
            "scenario": "refund",
        },
    ),
    Document(
        page_content=(
            "退货申请规则：客服应确认商品是否满足退货条件，并向用户说明申请入口、寄回要求、"
            "验收流程和退款处理方式。涉及质量问题时，应保留用户反馈和凭证。"
        ),
        metadata={
            "source_id": "return_application_rule",
            "title": "退货申请与寄回规则",
            "scenario": "return",
        },
    ),
    Document(
        page_content=(
            "运费咨询规则：客服应根据订单、活动和售后原因核实运费承担方；"
            "涉及退货运费时，应先说明适用条件和处理标准，再给出下一步指引。"
        ),
        metadata={
            "source_id": "freight_responsibility_rule",
            "title": "运费与退货运费处理规则",
            "scenario": "freight",
        },
    ),
]
