# 当前进度

## 项目状态

- 项目定位：电商售后客服 Copilot
- 当前阶段：M8 独立前端工作台
- 当前里程碑：M8.5 React 运营看板联调

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
- M8.1 前端工程骨架已完成：
  - 新增独立 `frontend/` Vite + React + TypeScript 工程
  - 已接入 Ant Design、React Router、Axios、Recharts 与 Vitest
  - 默认路由为 `/workspace`，已提供工单中心、Agent 追踪、运营看板四个静态页面入口
  - Vite 开发环境将 `/api` 代理至 `http://127.0.0.1:8001`
  - 已完成根路径重定向与工单中心导航的自动化测试
- M8.2 Copilot 工作台接口联调已完成：
  - `/workspace` 支持输入用户售后问题，并通过 Vite `/api` 代理调用 `POST /api/copilot/analyze`
  - 页面展示识别意图、订单号、物流异常判断、客服回复草稿、RAG 规则来源、工单结果、Run ID 与飞书通知状态
  - 已提供请求中、接口失败和无规则召回时的页面状态
  - Axios 客户端与 TypeScript 响应类型已集中到 `frontend/src/services/api.ts`
  - 已完成异常物流真实联调：`ORD-1001` 可返回 RAG 来源并创建催物流工单
- M8.3 React 工单中心联调已完成：
  - `/tickets` 已对接 `GET /api/tickets`，展示工单 ID、订单号、类型、优先级、状态、处理人和摘要
  - `/tickets/{ticketId}` 已展示工单详情、关联订单和物流信息、工单事件时间线
  - 新增 `POST /api/tickets/{ticket_id}/actions` JSON API，支持 `claim`、`resolve`、`reopen` 三种合法人工状态操作
  - 状态操作复用既有状态机，写入 `manual_status_changed` 工单事件；前端演示操作人固定为“客服A”
  - 已完成前端单元测试、构建和后端全量 pytest 验证
- M8.4 React Agent 追踪联调已完成：
  - 新增 `GET /api/runs`，按创建时间倒序返回 Agent Run 列表
  - `/runs` 已展示 Run ID、用户问题、意图、状态、总耗时和创建时间
  - `/runs/{runId}` 已展示 Run 执行概览与完整 Step 时间线
  - Step 时间线展示节点名称、类型、状态、耗时、输入摘要、输出摘要和失败信息
  - 已完成 Run 列表 API、前端列表到详情跳转、Step 链路渲染的自动化测试
  - Run 详情已升级为连续比例条式 Trace Waterfall：按 Step 耗时严格切分总时长，使用下方可点击图例与详情区展示节点信息
  - 新增 `POST /api/runs/demo-waterfall`：生成独立的 `RUN-DEMO-*` 示例链路，含 11 个固定耗时 Step，便于直观看到瀑布图区块比例

## 下一步

- M8.5：实现 `/dashboard`，对接现有 Dashboard API，完成前后端联调、Docker Compose 和验收。

## M8 约定

- 正式前端采用 Vite + React，与 FastAPI 前后端分离。
- `/workspace` 是默认首页；视觉参考 Intercom Inbox、Linear 和 LangSmith / Datadog。
- 保留 `/admin/*` 作为内部调试后台，不替代 React 前端。
- 当前无登录体系，人工操作先以演示操作人“客服A”记录；认证能力后续单独建设。

## 备注

这个文件记录当前状态，不记录长期规则。长期规则放在 `AGENTS.md`，总规划放在 `ecommerce_after_sales_copilot_plan.md`。
