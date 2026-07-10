# 当前进度

## 项目状态

- 项目定位：电商售后客服 Copilot
- 当前阶段：M4 飞书 Webhook V1 通知
- 当前里程碑：异常物流工单飞书通知

## 已完成

- `AGENTS.md` 已创建
- 项目总规划文档已存在：`ecommerce_after_sales_copilot_plan.md`
- FastAPI 应用入口已创建：`api/main.py`
- 健康检查接口已创建：`GET /health`
- SQLite 数据库初始化已创建：`models/database.py`
- 业务模型已创建：`orders`、`logistics`、`tickets`、`ticket_events`
- Agent 可观测性模型已创建：`agent_runs`、`agent_steps`
- 示例订单与物流种子数据已创建：
  - `ORD-1001`：物流异常，适合测试催物流工单
  - `ORD-1002`：物流正常，适合对比测试
- M1 基础 API 已创建：
  - `GET /api/orders/{order_id}`
  - `GET /api/logistics/{order_id}`
  - `POST /api/tickets`
  - `GET /api/tickets`
  - `GET /api/tickets/{ticket_id}`
  - `PATCH /api/tickets/{ticket_id}`
  - `POST /api/tickets/{ticket_id}/events`
- Agent run / step 查询 API 已创建：
  - `GET /api/runs/{run_id}`
  - `GET /api/runs/{run_id}/steps`
- Copilot 分析接口已创建：
  - `POST /api/copilot/analyze`
- LangGraph 编排已接入：
  - `intent_node`
  - `order_extract_node`
  - `order_query_node`
  - `logistics_query_node`
  - `abnormal_check_node`
  - `policy_retrieval_node`
  - `reply_generate_node`
  - `ticket_create_node`
- RAG 知识库检索已接入：
  - 本地售后知识库
  - LangChain + FAISS 检索
  - deterministic embedding，暂不依赖外部 LLM 或付费 embedding API
  - `policy_retrieval` step 写入 Agent 执行链路
- 飞书 Webhook V1 通知已接入：
  - 未配置 `FEISHU_WEBHOOK_URL` 时默认跳过真实发送
  - 异常物流工单创建后记录 `feishu_notify` step
  - 飞书通知失败不影响 Copilot 主流程返回
  - `POST /api/copilot/analyze` 返回 `feishu_status`
- 自动化测试已覆盖：
  - 健康检查
  - 订单 / 物流 / 工单 API
  - Agent run / step API
  - Copilot analyze API
  - LangGraph workflow
  - RAG policy retrieval
  - 飞书 Webhook disabled / failed / trace 记录

## 下一步

- 做最小客服后台页面，用于展示订单、物流、工单、Agent run 和 step
- 或继续增强飞书 M5：交互卡片按钮回调、状态流转和 `feishu_events`

## 备注

这个文件记录当前状态，不记录长期规则。长期规则放在 `AGENTS.md`，总规划放在 `ecommerce_after_sales_copilot_plan.md`。
