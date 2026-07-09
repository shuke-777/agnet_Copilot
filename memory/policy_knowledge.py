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
]
