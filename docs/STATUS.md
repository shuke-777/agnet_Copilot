# 当前进度

## 项目状态

- 项目定位：电商售后客服 Copilot
- 当前阶段：M8 独立前端工作台
- 当前里程碑：前端工程与页面设计

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
- M3 最小客服后台页面已接入：
  - `GET /admin/tickets` 展示工单列表、订单号、商品、优先级、状态和摘要
  - `GET /admin/tickets/{ticket_id}` 展示工单详情、订单物流信息和工单事件时间线
  - `GET /admin/runs` 展示 Agent run 列表
  - `GET /admin/runs/{run_id}` 展示 Agent run 详情和 step 执行链路
- 测试数据库已隔离：
  - pytest 使用 `data/test.db`
  - 本地服务继续使用 `data/app.db`
- M5 飞书交互回调已接入：
  - 新增 `feishu_events` 表，记录回调动作和处理结果
  - `POST /api/feishu/callback` 支持 `claim`、`resolve`、`reopen`
  - 回调成功后同步更新 `tickets.status`
  - 同时记录 `ticket_events` 和 `feishu_events`
  - 非法状态流转返回 HTTP 409
- M6 RAG 售后知识库已扩展：
  - 新增发货时效、退款、退货、运费和客服话术知识
  - 新增 deterministic Query 改写，补充售后意图和物流上下文
  - 检索链路拆分为 `query_rewrite`、`policy_retrieval`、`policy_rerank` 三个 Agent step
  - 重排序优先匹配当前售后意图，避免物流背景覆盖退款、退货等规则
  - 退款、退货、运费和发货时效场景生成知识库引用的回复草稿
  - 当前仅物流异常场景自动创建催物流工单；退款、退货等交易操作仍待后续业务模块实现
- M7 Dashboard API 已接入：
  - `GET /api/dashboard/overview`：工单、Agent Run 和飞书通知核心指标
  - `GET /api/dashboard/ticket-stats`：工单状态与优先级分布
  - `GET /api/dashboard/agent-performance`：Agent Run 与 Step 耗时、成功率
  - 飞书通知成功率仅统计实际发送的 `success` / `failed` 记录，排除未配置 Webhook 的 `skipped`
- M7 Dashboard 页面已接入：
  - `GET /admin/dashboard` 展示运营概览、工单状态/优先级分布和 Agent Step 性能
  - 后台导航新增“运营看板”入口
- 工单后台人工处理已接入：
  - `/admin/tickets` 支持按状态、优先级筛选
  - 工单列表展示处理人和更新时间
  - 工单详情支持接单、解决、重新打开三个合法状态操作
  - 后台操作写入 `ticket_events`，事件类型为 `manual_status_changed`
  - 飞书回调继续额外写入 `feishu_events`，便于区分外部回调与后台人工处理
- M7 README 与本地部署材料已完成：
  - README 已补充架构、启动方式、Docker Compose、演示流程、RAG、接口、测试和项目边界
  - 已新增 `Dockerfile`、`docker-compose.yml` 和 `.dockerignore`
  - `docker compose config --quiet` 已验证通过
- 自动化测试已覆盖：
  - 健康检查
  - 订单 / 物流 / 工单 API
  - Agent run / step API
  - Copilot analyze API
  - LangGraph workflow
  - RAG policy retrieval
  - 飞书 Webhook disabled / failed / trace 记录
  - 飞书按钮回调、状态流转和事件记录
  - 最小客服后台页面

## 下一步

- M8.1：创建 `frontend/` 独立 Vite + React + TypeScript 工程，接入 Ant Design、React Router、Axios 和 Recharts。
- M8.2：实现默认首页 `/workspace`，调用 `POST /api/copilot/analyze` 并展示 Copilot 分析、RAG 引用、工单与 Run 结果。
- M8.3：实现 `/tickets`、`/tickets/{ticketId}`，补充面向独立前端的人工状态流转 JSON API。
- M8.4：实现 `/runs`、`/runs/{runId}`，补充 `GET /api/runs` 并展示 Agent Step 执行链路。
- M8.5：实现 `/dashboard`，对接现有 Dashboard API，完成前后端联调、Docker Compose 和验收。

## M8 约定

- 正式前端采用 Vite + React，与 FastAPI 前后端分离。
- `/workspace` 是默认首页；视觉参考 Intercom Inbox、Linear 和 LangSmith / Datadog。
- 保留 `/admin/*` 作为内部调试后台，不替代 React 前端。
- 当前无登录体系，人工操作先以演示操作人“客服A”记录；认证能力后续单独建设。

## 备注

这个文件记录当前状态，不记录长期规则。长期规则放在 `AGENTS.md`，总规划放在 `ecommerce_after_sales_copilot_plan.md`。
