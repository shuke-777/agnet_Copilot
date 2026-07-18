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
    Document(
        page_content=(
            "签收争议处理 SOP：物流显示已签收但用户反馈未收到时，客服应先核对签收人、"
            "签收地点和代收点信息，引导用户确认同住人、前台或门店代收情况；仍未找到时，"
            "记录签收争议并联系承运商核查，不直接承诺补发或退款。"
        ),
        metadata={
            "source_id": "delivery_dispute_signed_sop",
            "title": "签收争议与用户未收到处理 SOP",
            "scenario": "normal_logistics",
        },
    ),
    Document(
        page_content=(
            "未发货催发 SOP：订单已付款但尚未发货时，客服应核实承诺发货时效、仓库状态"
            "和缺货风险；若超过承诺时效，应记录催发请求并同步预计处理时间，"
            "不得将未发货问题误判为物流运输异常。"
        ),
        metadata={
            "source_id": "paid_not_shipped_followup_sop",
            "title": "已付款未发货催发处理 SOP",
            "scenario": "shipping_timeliness",
        },
    ),
    Document(
        page_content=(
            "高金额退款审核规则：高金额订单申请退款时，客服应核实支付状态、发货状态、"
            "售后申请记录和风险标记，并进入人工审核；审核通过前，Agent 只能给出处理建议，"
            "不能直接承诺退款成功或执行资金动作。"
        ),
        metadata={
            "source_id": "high_value_refund_approval_rule",
            "title": "高金额退款人工审核规则",
            "scenario": "refund",
        },
    ),
    Document(
        page_content=(
            "仅退款处理边界：用户申请仅退款时，应区分未发货、运输中、已签收和质量问题场景；"
            "涉及已发货或已签收订单时，需人工确认责任和凭证，不能直接跳过审核。"
        ),
        metadata={
            "source_id": "refund_only_boundary_rule",
            "title": "仅退款处理边界规则",
            "scenario": "refund",
        },
    ),
    Document(
        page_content=(
            "退货验收规则：退货申请应说明寄回要求、商品完好标准、凭证保留和仓库验收流程；"
            "退款应在仓库验收通过后继续处理，质量问题需记录用户描述和图片凭证。"
        ),
        metadata={
            "source_id": "return_inspection_rule",
            "title": "退货寄回与仓库验收规则",
            "scenario": "return",
        },
    ),
    Document(
        page_content=(
            "换货处理规则：用户申请换货时，客服应确认商品状态、换货原因、库存情况和寄回要求；"
            "涉及重新发货或库存占用，需进入人工审核，不由 Agent 直接执行重发。"
        ),
        metadata={
            "source_id": "exchange_processing_rule",
            "title": "换货申请与库存审核规则",
            "scenario": "exchange",
        },
    ),
    Document(
        page_content=(
            "改地址风险规则：订单发货后申请改地址时，客服应先核实物流阶段和承运商是否支持改派；"
            "运输中改地址可能产生履约风险，应进入人工审核并记录用户确认信息。"
        ),
        metadata={
            "source_id": "address_change_risk_rule",
            "title": "发货后改地址风险审核规则",
            "scenario": "address_change",
        },
    ),
    Document(
        page_content=(
            "取消订单规则：未发货订单可核实是否支持取消；已发货订单通常需要结合拦截、拒收或退货流程处理。"
            "取消订单涉及交易状态变更，需人工审核后推进。"
        ),
        metadata={
            "source_id": "order_cancel_approval_rule",
            "title": "取消订单人工审核规则",
            "scenario": "cancel_order",
        },
    ),
    Document(
        page_content=(
            "补偿赔付审核规则：涉及补偿、赔付、优惠券、差价或额外权益时，客服应记录原因、金额或权益类型，"
            "并提交人工审核；Agent 只能建议处理方向，不直接发放补偿。"
        ),
        metadata={
            "source_id": "compensation_approval_rule",
            "title": "补偿与赔付人工审核规则",
            "scenario": "compensation",
        },
    ),
    Document(
        page_content=(
            "投诉升级规则：用户表达强烈不满、重复投诉或要求平台介入时，应提高响应等级，"
            "记录核心诉求和已处理动作，并转交人工主管或二线客服继续跟进。"
        ),
        metadata={
            "source_id": "complaint_escalation_rule",
            "title": "投诉升级与二线介入规则",
            "scenario": "general_reply",
        },
    ),
]
