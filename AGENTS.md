# AGENTS.md

本文件为 Codex 在此仓库中处理代码、文档和测试时提供协作准则。

## 项目定位

这是一个面向电商客服团队的售后工单 Copilot 项目。

它不是普通聊天机器人，而是帮助客服完成售后处理闭环：

- 查订单
- 查物流
- 判断售后规则
- 生成客服回复草稿
- 创建和更新工单
- 推送飞书协同
- 记录每一步 Agent 执行耗时
- 支持人工 checkpoint 和状态流转

核心原则：

> Agent 负责识别、查询、判断、建议；人工负责确认、处理、推进状态；系统负责记录全过程。

## 当前 MVP 范围

第一阶段只聚焦一个可测试闭环：

```text
订单没收到 / 物流异常 / 催物流工单
```

优先跑通：

```text
客服输入用户问题
-> Agent 识别意图
-> 提取订单号
-> 查询订单
-> 查询物流
-> 判断是否异常
-> 生成客服回复草稿
-> 如需后续处理，创建工单
-> 记录 Agent run 和 step 耗时
-> 用户测试接口结果
```

退款、退货、换货、投诉、复杂 RAG、完整飞书交互和性能看板都放在后续里程碑。

## 开发节奏

本项目采用小步快跑，用户边测边反馈。

每个里程碑结束时必须停下来，提供：

- 本次完成了什么
- 如何启动服务
- 如何测试
- 示例请求
- 预期返回
- 已运行的验证命令和结果

推荐里程碑顺序：

1. 项目骨架与本地启动
2. M1 基础业务系统：订单、物流、工单、工单事件
3. Agent run / step 埋点框架
4. M2 物流异常 Copilot 闭环
5. M3 后台最小页面
6. M4-M5 飞书通知与按钮回调
7. M6-M7 RAG、性能看板、README 和展示材料

不要一次性堆完全部功能。

## 技术默认

除非用户明确要求变更，默认采用：

- 后端：Python、FastAPI、Pydantic、SQLAlchemy
- 数据库：SQLite first，后续再迁移 PostgreSQL
- Agent：LangGraph，可先用 deterministic mock agent 跑通闭环
- RAG：FAISS first，后续可替换 pgvector / Milvus / Qdrant
- 前端：React / Next.js、Ant Design、Recharts 或 ECharts
- 协同：飞书 Webhook V1，后续接交互卡片和回调
- 部署：Docker Compose

第一版允许先不接真实 LLM 和真实电商平台接口，用可替换封装和模拟数据保证业务链路可测试。

## 开发前必须阅读

在实现任何功能前，先阅读：

- `ecommerce_after_sales_copilot_plan.md`
- 本文件 `AGENTS.md`

如果两者冲突：

1. 用户最新明确要求优先
2. `AGENTS.md` 的协作规则优先
3. `ecommerce_after_sales_copilot_plan.md` 的产品和技术规划优先
4. 现有代码实现作为参考，但不要盲目继承明显错误

## 协作规则

- 功能开发前先做设计，明确目标、范围、成功标准和验收方式。
- 写实现代码前先写测试或至少明确可执行的验证命令。
- 完成前必须运行验证命令，并在回复中说明验证结果。
- 修改范围要小，优先完成当前里程碑。
- 不要重构无关代码。
- 不要覆盖用户已有改动。
- 不要删除、重置或清理工作区中的未知文件，除非用户明确要求。
- 如果遇到需求不清、外部凭据缺失或真实平台接入风险，先说明阻塞点和建议。

## 数据与 API 优先级

第一阶段优先实现这些表或等价模型：

- `orders`
- `logistics`
- `tickets`
- `ticket_events`
- `agent_runs`
- `agent_steps`

第一阶段优先稳定这些 API：

- `GET /health`
- `GET /api/orders/{order_id}`
- `GET /api/logistics/{order_id}`
- `POST /api/tickets`
- `GET /api/tickets`
- `GET /api/tickets/{ticket_id}`
- `PATCH /api/tickets/{ticket_id}`
- `POST /api/tickets/{ticket_id}/events`
- `POST /api/copilot/analyze`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/steps`

飞书相关的 `feishu_events` 和回调接口放到飞书里程碑再实现。

## 测试要求

每个里程碑至少包含一种自动验证和一种手工验收方式。

推荐测试层次：

- 单元测试：服务函数、状态流转、异常判断、订单号提取
- API 测试：FastAPI TestClient 验证状态码和返回结构
- 手工验收：Swagger 或 curl 测试完整业务流程

典型验收场景：

- 正常订单查询
- 物流正常时不创建工单
- 物流异常时自动创建催物流工单
- 工单状态从 `todo` 到 `processing` 到 `resolved`
- Copilot run 能追踪所有 step 耗时

## 禁止事项

- 不要先做复杂前端，再补后端业务闭环。
- 不要在没有用户确认的情况下接真实电商平台、真实飞书群或真实 LLM 计费接口。
- 不要把示例项目、无关脚本或其它仓库的配置复制进来。
- 不要为了展示效果牺牲可观测性和可测试性。
- 不要声称完成但没有运行验证。

## README 边界

本文件是项目协作规则，不替代正式 README。

README、架构图、运行截图、测试用例说明和 GitHub 展示文档放到 M7 阶段集中完善。
