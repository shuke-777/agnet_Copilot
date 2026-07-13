from datetime import timedelta

from sqlalchemy.orm import Session

from models.agent_trace import AgentRun, AgentStep
from models.business import utc_now
from services.trace_service import make_trace_id


DEMO_WATERFALL_STEPS = (
    ("intent_recognition", "agent", "success", 55, "识别用户售后意图", "识别为物流异常催单"),
    ("order_extract", "agent", "success", 20, "提取订单号", "ORD-1001"),
    ("order_query", "tool", "success", 85, "查询订单 ORD-1001", "订单已发货"),
    ("logistics_query", "tool", "success", 120, "查询物流 ORD-1001", "物流 72 小时未更新"),
    ("abnormal_check", "agent", "success", 45, "判断物流是否异常", "确认物流异常"),
    ("query_rewrite", "rag", "success", 130, "改写售后知识库检索词", "物流异常催单处理规范"),
    ("policy_retrieval", "rag", "success", 620, "检索售后知识库", "召回物流异常 SOP 与客服话术"),
    ("policy_rerank", "rag", "success", 340, "重排序检索结果", "物流异常 SOP 排名第一"),
    ("reply_generate", "agent", "success", 120, "生成客服回复草稿", "已生成安抚与处理时效说明"),
    ("ticket_create", "tool", "success", 90, "创建催物流工单", "示范工单创建成功"),
    ("feishu_notify", "webhook", "success", 120, "发送飞书工单通知", "飞书群通知发送成功"),
)


def create_demo_waterfall_run(db: Session) -> AgentRun:
    """Create an isolated, fixed-duration trace for the frontend waterfall demo."""
    started_at = utc_now()
    total_duration_ms = sum(step[3] for step in DEMO_WATERFALL_STEPS)
    run = AgentRun(
        run_id=make_trace_id("RUN-DEMO"),
        session_id="DEMO-WATERFALL",
        user_id="DEMO-USER",
        user_message="瀑布图示范链路：订单 ORD-1001 未收到",
        intent="logistics_delay",
        status="success",
        total_duration_ms=total_duration_ms,
        created_at=started_at,
        finished_at=started_at + timedelta(milliseconds=total_duration_ms),
    )
    db.add(run)

    current_time = started_at
    for step_name, step_type, status, duration_ms, input_summary, output_summary in DEMO_WATERFALL_STEPS:
        end_time = current_time + timedelta(milliseconds=duration_ms)
        db.add(
            AgentStep(
                step_id=make_trace_id("STP"),
                run_id=run.run_id,
                step_name=step_name,
                step_type=step_type,
                status=status,
                start_time=current_time,
                end_time=end_time,
                duration_ms=duration_ms,
                input_summary=input_summary,
                output_summary=output_summary,
            )
        )
        current_time = end_time

    db.commit()
    db.refresh(run)
    return run
