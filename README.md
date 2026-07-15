# 电商售后客服 Copilot

面向电商客服团队的售后工单 Copilot。项目聚焦「订单未收到 / 物流异常 / 催物流」场景，将订单查询、物流判断、售后规则检索、客服回复草稿、工单协同和 Agent 可观测性串成可测试的闭环。

> Agent 负责识别、查询、判断和建议；人工负责确认、处理和推进状态；系统负责记录全过程。

## 功能概览

- 基础业务：订单、物流、工单、工单事件的 RESTful API。
- Copilot 工作流：使用 LangGraph 依次执行意图识别、订单提取、订单/物流查询、异常判断、回复生成和工单创建。
- RAG 知识库：使用 LangChain + FAISS 检索物流、发货、退款、退货、运费和客服话术规则；当前使用本地 deterministic embedding，无需外部模型或 API Key。
- 可观测性：记录每次 Agent Run 和每个 Step 的状态、输入输出摘要与耗时。
- 协同处理：异常物流工单可发送飞书 Webhook 通知；飞书回调和后台页面共享工单状态机。
- 客服后台：查看工单、处理状态流转、追踪 Agent Run，并通过运营看板查看工单与 Step 性能指标。

## 架构

```text
客服问题
  -> FastAPI /api/copilot/analyze
  -> LangGraph 工作流
     -> 订单与物流查询（SQLite）
     -> RAG 检索与重排序（LangChain + FAISS）
     -> 回复草稿与工单决策
     -> 飞书 Webhook（可选）
  -> SQLite：业务数据、工单事件、Agent Run / Step、飞书回调事件

客服后台 /admin/tickets、/admin/runs、/admin/dashboard
  -> FastAPI 服务端渲染页面与 Dashboard API
```

当前只有「物流异常」意图会自动创建催物流工单。退款、退货、运费、发货时效问题会基于知识库生成回复草稿，不会执行真实交易操作。

## 技术栈

`Python`、`FastAPI`、`SQLAlchemy`、`Pydantic`、`SQLite`、`LangGraph`、`LangChain`、`FAISS`、`pytest`、飞书 Webhook、`Docker Compose`。

## 快速启动

### 方式一：本地 Python 环境

项目当前使用的 Conda 环境为 `rag_910`。在项目根目录运行：

```bash
/opt/anaconda3/envs/rag_910/bin/uvicorn api.main:app \
  --host 127.0.0.1 \
  --port 8001 \
  --reload
```

若通过 PyCharm 直接运行 [`api/main.py`](api/main.py)，文件内的启动入口同样会启动服务；日常开发仍建议使用上面的 Uvicorn 命令。

### 方式二：Docker Compose

需要本机已经启动 Docker Desktop。在项目根目录运行：

```bash
docker compose up --build
```

首次启动会构建后端与 React 前端镜像，并创建 `data/app.db`。`./data` 会挂载到容器内，因此重启容器不会丢失工单、Agent Run 与其他本地数据。浏览器访问前端后，Nginx 会将 `/api/*` 请求转发到 FastAPI 容器。

后台运行：

```bash
docker compose up --build -d
```

停止服务：

```bash
docker compose down
```

查看日志：

```bash
docker compose logs -f copilot
```

默认不会发送真实飞书消息。只有在启动前显式配置 Webhook 才会发送：

```bash
export FEISHU_WEBHOOK_URL='你的飞书机器人 Webhook 地址'
docker compose up --build
```

## 访问入口

服务启动后访问：

| 页面或接口 | 地址 |
| --- | --- |
| Swagger API 文档 | `http://127.0.0.1:8001/docs` |
| 健康检查 | `http://127.0.0.1:8001/health` |
| React Copilot 工作台 | `http://127.0.0.1:5173/workspace` |
| React 工单中心 | `http://127.0.0.1:5173/tickets` |
| React Agent 追踪 | `http://127.0.0.1:5173/runs` |
| React 运营看板 | `http://127.0.0.1:5173/dashboard` |
| 客服工单后台 | `http://127.0.0.1:8001/admin/tickets` |
| Agent Run 后台 | `http://127.0.0.1:8001/admin/runs` |
| 运营看板 | `http://127.0.0.1:8001/admin/dashboard` |

应用首次启动时会写入两条演示数据：

- `ORD-1001`：物流异常，用于测试自动创建催物流工单。
- `ORD-1002`：物流正常，用于测试不创建工单的流程。

## 可选：接入真实 LLM

默认配置为 `LLM_PROVIDER=disabled`，系统不会发出模型请求，并完整保留确定性意图识别、订单号提取、查询改写和回复模板逻辑。

在项目根目录创建 `.env`，并参考 [`.env.example`](.env.example) 写入所需变量。后端启动后会自动读取该文件；终端或 PyCharm Run Configuration 中显式设置的同名变量优先级更高。

```bash
# OpenAI-compatible 服务
export LLM_PROVIDER=openai_compatible
export LLM_BASE_URL='https://你的服务地址/v1'
export LLM_API_KEY='你的密钥'
export LLM_MODEL='你的模型名'
```

```bash
# 本地 Ollama
export LLM_PROVIDER=ollama
export LLM_BASE_URL='http://127.0.0.1:11434'
export LLM_MODEL='qwen3:8b'
```

Gateway 仅将真实模型用于意图识别、订单号提取、RAG 查询改写和客服回复草稿。订单/物流查询、异常判断、建单、工单状态流转和飞书通知仍由确定性业务代码执行。模型超时、网络失败、无效 JSON 或结构化结果不合格时，系统会自动降级到确定性逻辑；Run Step 会记录 provider、model、Token 用量和降级原因。

## 可选：启用 Redis

M10 的 Redis 接入是可选的。未配置或未启动 Redis 时，后端仍可正常启动，`GET /health` 会返回 `redis.status = disabled` 或 `unavailable`。后续限流、Dashboard 缓存和运营风险榜会在 Redis 可用时自动启用。

本机已启动 Redis 后，在 `.env` 中配置：

```bash
REDIS_URL=redis://127.0.0.1:6379/0
REDIS_CONNECT_TIMEOUT_SECONDS=1
COPILOT_RATE_LIMIT_CAPACITY=10
COPILOT_RATE_LIMIT_WINDOW_SECONDS=60
SESSION_CONTEXT_TTL_SECONDS=1800
SESSION_CONTEXT_MAX_MESSAGES=10
```

重启后端，再访问 `http://127.0.0.1:8001/health`；成功连接时会返回 `redis.status = connected`。无需在当前阶段修改 Docker Compose。

Redis 连通后，`POST /api/copilot/analyze` 默认按 `user_id` 采用令牌桶限制为每 60 秒 10 次；请求没有 `user_id` 时按客户端 IP 兜底。超限时接口返回 HTTP `429`、`Retry-After` 和可重试秒数，React 工作台会直接提示等待时间。Redis 未配置或不可用时，限流自动降级放行，避免影响本地开发。

Redis 也会按 `session_id` 保存 Copilot 短期上下文，默认保留 30 分钟、最多 10 条消息。上下文只包含用户/助手文本和最近识别到的订单号；同一 `session_id` 但 `user_id` 不一致时不会读取已有上下文。订单、物流、工单等完整业务对象仍只从数据库按业务权限读取，不进入会话缓存。Redis 不可用时，系统继续使用前端传入的 `history` 和数据库最近 Run 作为订单号识别的降级来源。

## 演示流程

### 1. 提交异常物流问题

```bash
curl -s -X POST http://127.0.0.1:8001/api/copilot/analyze \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id": "SESSION-DEMO-001",
    "user_id": "USER-001",
    "user_message": "我的订单 ORD-1001 怎么还没收到？帮我催一下物流。"
  }'
```

预期结果：返回 `ticket_created: true`、新生成的 `ticket_id` 和 `run_id`；未配置飞书 Webhook 时，`feishu_status` 为 `disabled`。

### 2. 查看执行链路

将上一步返回的 `run_id` 代入：

```bash
curl -s http://127.0.0.1:8001/api/runs/{run_id}/steps
```

可看到以下 Step：

```text
intent -> order_extract -> order_query -> logistics_query -> abnormal_check
-> query_rewrite -> policy_retrieval -> policy_rerank -> reply_generate
-> ticket_create -> feishu_notify
```

### 3. 在后台人工处理工单

打开 `http://127.0.0.1:8001/admin/tickets`，进入新建工单详情页。根据当前状态可执行「接单」「解决」「重新打开」操作；后台会写入 `manual_status_changed` 工单事件。

### 4. 模拟飞书回调

使用步骤 1 返回的真实 `ticket_id`：

```bash
curl -s -X POST http://127.0.0.1:8001/api/feishu/callback \
  -H 'Content-Type: application/json' \
  -d '{
    "event_id": "FEISHU-EVENT-DEMO-001",
    "ticket_id": "TCK-替换为真实工单ID",
    "action": "claim",
    "operator": "客服A"
  }'
```

支持的状态转换：

| 动作 | 状态变化 |
| --- | --- |
| `claim` | `todo -> processing` |
| `resolve` | `processing -> resolved` |
| `reopen` | `resolved -> processing` |

成功回调会更新工单，并分别写入 `ticket_events` 与 `feishu_events`，用于区分业务审计与外部回调审计。

## RAG 说明

本项目的 RAG 链路为：

```text
用户问题 -> query_rewrite -> FAISS 召回 -> deterministic 词法重排序 -> 回复草稿
```

知识库位于 [`memory/policy_knowledge.py`](memory/policy_knowledge.py)，当前覆盖物流异常、正常物流、发货时效、退款、退货、运费和客服安抚话术。当前实现不依赖真实 LLM 或付费 embedding 服务，方便本地演示和自动化测试；数据量与召回要求提升后，可将向量存储替换为 Milvus、pgvector 或 Qdrant，并接入真实 embedding 与 reranker。

可通过退款问题验证 RAG 不误建物流工单：

```bash
curl -s -X POST http://127.0.0.1:8001/api/copilot/analyze \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id": "SESSION-RAG-REFUND-001",
    "user_id": "USER-001",
    "user_message": "订单 ORD-1001 可以退款吗？"
  }'
```

预期结果：返回退款规则的 `policy_sources` 与回复草稿，但 `ticket_created` 为 `false`。

## 主要 API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/health` | 服务健康检查 |
| `GET` | `/api/orders/{order_id}` | 查询订单 |
| `GET` | `/api/logistics/{order_id}` | 查询物流 |
| `POST` | `/api/tickets` | 手工创建工单 |
| `GET` | `/api/tickets` | 查询工单列表 |
| `GET` | `/api/tickets/{ticket_id}` | 查询工单与事件 |
| `PATCH` | `/api/tickets/{ticket_id}` | 更新工单字段 |
| `POST` | `/api/copilot/analyze` | 执行 Copilot 分析闭环 |
| `GET` | `/api/runs/{run_id}` | 查询 Agent Run |
| `GET` | `/api/runs/{run_id}/steps` | 查询 Agent Step 链路 |
| `POST` | `/api/feishu/callback` | 模拟飞书卡片回调 |
| `GET` | `/api/dashboard/overview` | 查询运营概览 |

完整参数与响应结构请查看 Swagger：`http://127.0.0.1:8001/docs`。

## 测试

自动化测试使用独立的 `data/test.db`，不会污染本地服务使用的 `data/app.db`。

```bash
/opt/anaconda3/envs/rag_910/bin/python -m pytest -q
```

测试覆盖健康检查、订单/物流/工单 API、Copilot LangGraph 工作流、RAG 检索与重排序、飞书通知与回调、后台人工状态流转、Dashboard API 等关键路径。

## 项目文档

- [协作规则](AGENTS.md)
- [产品与技术规划](ecommerce_after_sales_copilot_plan.md)
- [当前实施状态](docs/STATUS.md)

## 当前边界与后续演进

- 当前使用 SQLite 和本地演示数据，未连接真实电商平台。
- 默认不调用真实飞书、LLM 或付费 embedding API；真实 LLM 仅在手动配置 Gateway 后启用。
- 当前仅对物流异常自动建单；退款、退货等真实交易状态机待后续扩展。
- 随着知识库规模增长，可将 FAISS 替换为 Milvus、pgvector 或 Qdrant，并接入真实 embedding 与 reranker。
