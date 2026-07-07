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

## 项目亮点

这个项目的竞争点不是“用了 Agent”，而是：

> 做了一个可观测、可追踪、可人工接管的电商售后 Agent 系统。

简历描述可以写成：

> 基于 LangGraph 构建电商售后客服 Copilot，集成订单/物流查询、售后规则判断、RAG 知识库、工单状态流转、飞书协同通知与 Agent 执行链路追踪，实现从用户诉求识别到人工审核闭环的半自动化售后处理系统。
