# 电商售后客服 Copilot 项目规划摘要

## 项目定位

做一个面向电商客服团队的售后工单 Copilot。

它不是单纯聊天机器人，而是帮助客服完成：

- 查订单
- 查物流
- 判断售后规则
- 生成客服回复草稿
- 创建和更新工单
- 推送飞书协同
- 记录每一步 Agent 执行耗时
- 支持人工 checkpoint 和状态流转

核心目标：

> Agent 负责识别、查询、判断、建议；人工负责确认、处理、推进状态；系统负责记录全过程。

## 核心业务闭环

第一版优先跑通一个最小闭环：

```text
客服输入用户问题
-> Agent 识别意图
-> 提取订单号
-> 查询订单
-> 查询物流
-> 判断是否异常
-> 生成客服回复草稿
-> 如需后续处理，创建工单
-> 推送飞书
-> 人工在后台/飞书更新状态
-> 系统记录工单事件和 Agent 每步耗时
```

第一阶段只重点做：

```text
订单没收到 / 物流异常 / 催物流工单
```

后续再扩展退款、退货、换货、投诉。

## 推荐技术栈

后端：

```text
Python
FastAPI
Pydantic
SQLAlchemy
SQLite first，后续 PostgreSQL
Redis 可选，用于会话和缓存
```

Agent：

```text
LangGraph
LangChain
OpenAI-compatible LLM
```

RAG：

```text
FAISS first
后续可换 pgvector / Milvus / Qdrant
```

工具层：

```text
MCP Tool Server
```

前端后台：

```text
React / Next.js
Ant Design
Recharts 或 ECharts
```

协同集成：

```text
飞书 Webhook V1
飞书交互卡片 + 回调 V2
真实飞书公网回调后置：本地闭环完成后再配置自建应用回调、HTTPS 域名和 Cloudflare Tunnel
```

部署：

```text
Docker Compose
```

## 建议模块划分

```text
api/
  main.py

agents/
  supervisor.py
  intent_router.py
  order_agent.py
  logistics_agent.py
  policy_agent.py
  ticket_agent.py
  reply_agent.py
  compliance_checker.py

services/
  order_service.py
  logistics_service.py
  ticket_service.py
  policy_service.py
  trace_service.py
  feishu_service.py

models/
  database.py
  order.py
  logistics.py
  ticket.py
  agent_run.py
  feishu_event.py

mcp/
  mcp_server.py
  tools.py

memory/
  short_term.py
  long_term.py

frontend/
  admin dashboard
```

## 核心数据库表

### orders

```text
order_id
user_id
product_name
amount
status
paid_at
shipped_at
delivered_at
created_at
```

### logistics

```text
logistics_id
order_id
carrier
tracking_no
status
last_event
last_event_time
is_abnormal
created_at
updated_at
```

### tickets

```text
ticket_id
source_run_id
ticket_type
priority
status
user_id
order_id
summary
suggested_action
assigned_to
created_by
created_at
updated_at
```

### ticket_events

```text
event_id
ticket_id
event_type
operator
content
from_status
to_status
created_at
```

### agent_runs

```text
run_id
session_id
user_id
order_id
user_message
intent
status
total_duration_ms
created_at
finished_at
```

### agent_steps

```text
step_id
run_id
step_name
step_type
status
start_time
end_time
duration_ms
input_summary
output_summary
error_message
```

### feishu_events

```text
event_id
ticket_id
run_id
event_type
target
message_id
send_status
action
clicked_at
callback_received_at
db_updated_at
duration_ms
raw_payload
created_at
```

## 第一版 API

基础业务接口：

```text
GET  /api/orders/{order_id}
GET  /api/logistics/{order_id}

POST /api/tickets
GET  /api/tickets
GET  /api/tickets/{ticket_id}
PATCH /api/tickets/{ticket_id}
POST /api/tickets/{ticket_id}/events
```

Agent 接口：

```text
POST /api/copilot/analyze
GET  /api/runs?q=
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/steps
```

飞书接口：

```text
POST /api/feishu/webhook/test
POST /api/feishu/callback
GET  /api/feishu/events
```

后台接口：

```text
GET /api/dashboard/overview
GET /api/dashboard/agent-performance
GET /api/dashboard/ticket-stats
```

## 后台系统页面

### 1. Copilot 运行详情页

展示一次 Agent 执行链路：

```text
意图识别耗时
订单查询耗时
物流查询耗时
Query 改写耗时
HyDE 生成耗时
向量检索耗时
重排序耗时
规则判断耗时
回复生成耗时
合规检查耗时
工单创建耗时
飞书通知耗时
```

每一步显示：

```text
状态
开始时间
结束时间
duration_ms
输入摘要
输出摘要
错误信息
```

### 2. 工单管理页

展示：

```text
工单号
订单号
用户ID
类型
优先级
状态
创建时间
更新时间
处理人
是否推送飞书
```

支持筛选：

```text
todo
processing
waiting_user
waiting_vendor
resolved
closed
```

### 3. 工单详情页

展示工单时间线：

```text
Agent 创建工单
推送飞书成功
人工接单
状态改为处理中
追加处理记录
状态改为已解决
关闭工单
```

### 4. 飞书协同记录页

展示：

```text
飞书消息发送时间
发送耗时
发送状态
群/用户
消息 ID
按钮点击时间
回调接收时间
数据库更新时间
点击到更新状态的总耗时
```

### 5. 性能看板

展示：

```text
今日请求数
平均 Agent 总耗时
各 Agent step 平均耗时
工单创建成功率
飞书通知成功率
待处理工单数量
高优先级工单数量
LLM 调用失败率
```

## 小步快跑路线

### M1：基础业务系统

```text
订单查询
物流查询
工单创建/查询/更新
工单事件追加
SQLite 数据库
Swagger 可单独测试
agent_runs / agent_steps 埋点框架
```

### M2：物流异常 Agent 闭环

```text
支持“订单没收到”
提取订单号
查订单
查物流
判断异常
生成回复草稿
必要时创建催物流工单
记录每一步耗时
```

### M3：后台最小页面

```text
Copilot 运行详情
工单列表
工单详情时间线
```

### M4：飞书通知

```text
高优先级/异常工单推送飞书群
记录 feishu_events
```

### M5：飞书按钮回调

```text
飞书卡片按钮
接单/处理中/已解决
回调更新 tickets
追加 ticket_events
记录更新时间
```

### M6：RAG 售后知识库

```text
发货时效规则
退款规则
退货规则
运费规则
客服话术规范
Query 改写
HyDE 可选
检索和重排序耗时记录
```

### M7：性能看板与 README

```text
dashboard 指标
架构图
运行截图
测试用例
GitHub 展示文档
```

### M8：独立前端工作台

```text
技术栈：Vite + React + TypeScript + Ant Design + React Router + Axios + Recharts
前后端分离：frontend/ 独立工程，通过 REST API 调用 FastAPI
默认首页：Copilot 工作台，输入客服问题并展示分析、回复草稿、RAG 引用、工单和 Agent Run
工单中心：工单列表、状态/优先级筛选、工单详情、事件时间线、人工状态流转
Agent 追踪：Run 列表、Run 详情和 Step 执行链路
运营看板：对接现有 Dashboard API，展示工单分布和 Agent 性能
后端补充：GET /api/runs 和 POST /api/tickets/{ticket_id}/actions/{action}
保留 /admin/* 作为内部调试后台，React 前端作为正式业务界面
Docker Compose 同时启动前后端服务
```

视觉方向：

```text
工作台参考 Intercom Inbox：输入、分析结果和业务上下文并列呈现
工单中心参考 Linear：高信息密度、状态与优先级清晰
Agent 追踪参考 LangSmith / Datadog：Step 时间线、耗时、输入输出与错误可见
统一使用深色侧边导航、浅灰工作区、白色内容面；蓝绿色表示主操作，红橙色仅用于异常和高优先级
```

### M8.6：前端业务关联与连续咨询

```text
数据关联：tickets.source_run_id 关联首次自动建单的 Agent Run；agent_runs.order_id 记录本轮识别订单
SQLite 迁移：启动时无损补列、补索引，并从历史 ticket_create Step 回填可识别关联
统一检索：工单中心与 Agent 追踪均支持 TCK-、RUN-、ORD- 三类 ID 查询
工单中心：新增来源 Run、Agent 调用时间和跳转至 Trace Waterfall 的入口
Agent 追踪：工单 ID 放在第一列，可跳转工单详情；未建单 Run 明确显示“未创建工单”
连续咨询：同一 session_id 支持按顺序发送多轮消息，每轮独立创建 Agent Run
会话上下文：请求携带有限轮次历史；当前消息缺少订单号时可从会话内最近消息回退识别
新建咨询：工作台标题右侧提供显性按钮，生成新的 session_id 并清空当前会话，不删除历史 Run 和工单
跨页状态：分析任务、会话结果与错误状态提升到路由外的全局 Context；跳转页面后任务继续执行
全局提示：其他页面顶部显示分析中、已完成或失败状态；完成后工单中心与 Agent 追踪自动刷新
```

### M9：真实 LLM Gateway

```text
新增统一 LLM Gateway，业务节点不直接依赖具体模型供应商
支持 openai_compatible、ollama、disabled 三种模式，通过环境变量配置 provider、base_url、api_key 和 model
真实模型优先承担意图识别、订单号提取、RAG 查询改写和客服回复草稿生成
订单/物流查询、异常判断、建单、状态流转和飞书通知继续由确定性业务代码执行
Pydantic 校验模型结构化输出；超时、有限重试或输出不合格时降级为 deterministic 逻辑
记录模型名称、耗时、token 用量和失败原因到 Agent step，支持后续成本与性能分析
密钥仅从环境变量读取，不写入代码、数据库或 Git
```

### M10：Redis 性能、缓存与可靠性

```text
使用 Redis 实现 POST /api/copilot/analyze 的令牌桶限流，优先按 user_id 限制，并以 IP 作为兜底
超限返回 HTTP 429 和可重试时间，保护真实 LLM 调用成本
缓存 Dashboard 统计结果 30-60 秒；建单、工单状态更新和飞书回调后主动失效
M10.4 RAG 精确缓存：缓存 query_rewrite、policy_retrieval、policy_rerank；缓存键包含问题哈希、intent、物流异常状态、知识库版本和 Prompt/规则版本
RAG 命中缓存时仍记录对应 Agent step，并标记 cache_hit，保证 Trace 中的执行链路完整；不缓存完整回复、订单、物流和工单等动态或敏感数据
M10.5 会话上下文隔离（已完成）：Redis 按 session_id 保存短期多轮上下文，默认 30 分钟、最多 10 条消息；只保存用户/助手文本和最近订单号，同一 session_id 的 user_id 不一致时不读取上下文。接入认证后由 Token 解析 operator_id，未来多商家场景再扩展 tenant_id
公共售后 SOP 可在同一权限边界内共享缓存；订单、物流、工单等业务数据必须在权限校验后按用户/租户隔离，不能跨用户直接复用
M10.6 使用 Redis Sorted Set 维护运营风险榜：异常物流承运商风险榜、待处理高优先级工单榜和高频售后问题榜
M10.7 工单幂等与多 Run 关联（已完成）：同一权限边界内，同一订单的同类售后请求若已有 `todo` 或 `processing` 状态的工单，则复用该工单，不因连续追问、页面重复提交或请求重试重复建单
首次满足自动建单条件的 Run 创建工单并作为 `source_run_id`；后续复用该工单的 Run 写入 `agent_runs.ticket_id`，保证工单详情可以回看全部相关 Agent Run，Agent 追踪页也能展示同一个工单 ID
去重依据以业务实体为主：未来为 `tenant_id + order_id + ticket_type + 未关闭状态`，当前 MVP 在未接入租户体系前使用 `order_id + ticket_type + 未关闭状态`；`session_id` 只用于多轮上下文，不作为唯一去重条件
复用已有工单时写入明确的工单事件，例如 `copilot_followup_analyzed`，记录本轮 `run_id`、用户追问摘要和建议结果；不会重复推送飞书新建工单通知
复用工单时飞书新建工单通知明确跳过；飞书回调以 `event_id` 作为幂等键，重复事件直接返回首次处理结果，不重复推进状态或写入事件
M10.8 会话主工单绑定（计划中）：使用 SQLite 持久保存 `session_id + user_id + order_id -> ticket_id` 的活动主工单关系，Redis 只保存短期消息上下文。首次创建或复用催物流工单时建立绑定；同会话、同用户、同订单的物流追问或普通查询 Run 自动关联该 `ticket_id`，但不重复建单或发送飞书通知
催办表达以 `follow_up_requested` 业务信号记录，不直接把意图强制改为 `logistics_delay`；必须在订单和物流查询后同时满足“已发货、物流异常、明确催办”才创建或复用催物流工单，避免“催发货”被误建物流工单
同会话识别出不同订单时，接口返回 `session_order_mismatch`，前端要求用户点击“新建咨询”后再继续；不将新订单写入旧工单，也不在旧会话中创建新工单。退款、退货、运费等新的售后意图不自动关联已有物流工单
会话主工单仅在状态为 `todo` 或 `processing` 时自动关联；已解决工单保留历史关联但不再作为活动主工单。新增 `ticket_association` 返回值区分 `created`、`reused`、`session_linked`、`none` 和 `order_mismatch`
```

### M11：RabbitMQ 异步任务与可靠投递

```text
当前阶段先不做 M11；RabbitMQ 后置到真实飞书回调跑通之后
RabbitMQ 专门处理可靠异步任务，不与 Redis 的缓存、限流和排行榜职责重叠
异步处理飞书通知重试、长耗时 LLM 重试、外部平台同步和失败工单告警
定义任务消息、消费状态、有限重试、退避策略和死信队列
消费成功后更新 ticket_events 或 agent_steps，消费失败保留可追踪的错误信息
任务按 run_id、ticket_id 或 event_id 实现幂等，避免重复通知和重复业务动作
监控队列积压、消费耗时、重试次数和死信数量
```

### M12：实时事件推送（可选）

```text
使用 WebSocket 或 SSE 将 Copilot 执行进度、工单状态变化和异步任务结果推送到前端
前端工作台展示 Agent Step 实时状态，工单详情无需手动刷新即可看到飞书回调和异步任务结果
Redis Pub/Sub 可作为多实例事件分发能力；RabbitMQ 仍负责可靠任务投递
```

### M15：本地全链路验收与演示打磨

```text
当前优先执行 M15，目标是把本地项目打磨成 5-8 分钟可展示的简历项目闭环
使用 docs/LOCAL_DEMO.md 的 12 条问题逐条验收 Copilot 工作台、工单中心、Agent Trace 和 Dashboard
重点展示物流异常自动建单、正常物流不误建单、高金额退款人工审核、RAG 规则来源、Trace Waterfall 和风险看板
新增 docs/DEMO_SCRIPT.md，记录演示顺序、讲解重点、测试输入、预期结果和本地飞书审核模拟方式
验收中如果发现前端字段、RAG 召回、工单关联或审核状态不清晰，优先修影响演示理解的问题
```

### 最终交付材料

```text
M15 本地验收后，再集中整理 Docker Compose / README / 项目展示材料
README 覆盖本地启动、环境变量、前后端入口、核心 API、演示流程、项目亮点和当前边界
Docker Compose 完成前后端联合启动、浏览器验收和镜像构建验证
项目展示材料重点说明业务闭环、LangGraph 编排、RAG、人工审核、飞书协同和 Agent 可观测性
```

### M13：部署与真实飞书公网联调（后置）

```text
当前本地阶段继续使用 POST /api/feishu/callback 通过 Postman / curl 模拟 approve、reject、manual_confirm 审核动作
飞书真实卡片按钮点击依赖公网 HTTPS 回调地址，不作为本地功能验收阻塞项
本地核心功能和最终交付材料完成后，再将后端部署到服务器或通过 Cloudflare Tunnel 暴露服务
正式回调地址约定为 https://api.heyiweilai.top/api/feishu/callback
飞书自建应用中配置该回调地址，并订阅 card.action.trigger
后端适配飞书真实卡片回调 payload，复用现有工单审核和事件记录逻辑
飞书 Webhook、App Secret、Verification Token 等密钥只写入 .env，不写入代码、文档或数据库
真实飞书回调跑通后，再进入 RabbitMQ 可靠投递增强，处理通知重试、长耗时 LLM 重试和失败告警
```

## 项目亮点

这个项目的竞争点不是“用了 Agent”，而是：

> 做了一个可观测、可追踪、可人工接管的电商售后 Agent 系统。

简历描述可以写成：

> 基于 LangGraph 构建电商售后客服 Copilot，集成订单/物流查询、售后规则判断、RAG 知识库、工单状态流转、飞书协同通知与 Agent 执行链路追踪，实现从用户诉求识别到人工审核闭环的半自动化售后处理系统。
