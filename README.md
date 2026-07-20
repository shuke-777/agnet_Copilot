# 电商售后客服 Copilot

面向电商售后客服场景的 Agent 工单系统。项目围绕「订单未收到 / 物流异常 / 催物流 / 退款审核」等高频售后问题，将订单查询、物流判断、售后规则检索、客服回复草稿、工单状态流转、人工审核、飞书协同和 Agent 执行链路追踪沉淀为一个可观测、可测试、可人工接管的业务闭环。

> Agent 负责识别、查询、判断和建议；人工负责审核、确认和推进状态；系统负责记录全过程。

## 核心价值

- **业务闭环完整**：从用户售后问题进入 Copilot，到订单与物流查询、规则检索、回复生成、工单创建、人工处理和操作审计，形成端到端流程。
- **Agent 可观测**：每次 Copilot Run 都会记录 Step 输入摘要、输出摘要、状态、耗时、模型元数据和缓存命中情况，前端用 Trace Waterfall 展示执行链路。
- **RAG 有来源**：客服回复草稿会引用售后 SOP、审核规则和话术来源，避免只返回不可解释的生成内容。
- **高风险动作可审核**：退款、退货、换货、改地址、取消订单、补偿等诉求进入人工审核；Agent 不直接执行资金、库存或履约动作。
- **工程化可降级**：真实 LLM、Redis、飞书 Webhook 均为可选能力，未配置时系统仍能依靠确定性逻辑完成本地演示和自动化测试。

## 系统能力

| 模块 | 能力 |
| --- | --- |
| Copilot 工作台 | 输入售后问题，实时查看 Agent Step、识别意图、订单号、回复草稿、RAG 来源、工单和飞书状态 |
| 订单与物流 | 查询本地演示订单和物流轨迹，判断物流是否异常、是否超时、是否签收争议 |
| 工单中心 | 查看工单列表、详情、审核状态、事件时间线，支持接单、解决、重新打开和关联 Run 查询 |
| Agent 追踪 | 查看 Run 列表、工单 ID、订单 ID、总耗时、Step 明细和 Trace Waterfall |
| RAG 知识库 | 使用 LangChain + FAISS 检索售后 SOP、规则和话术，当前使用本地 deterministic embedding |
| LLM Gateway | 支持 `disabled`、OpenAI-compatible、Ollama 三种模式；失败时自动降级到确定性逻辑 |
| 飞书协同 | 支持 Webhook 通知、交互卡片消息结构和本地 callback 模拟审核 |
| 运营看板 | 展示工单指标、Agent 性能、飞书通知成功率、风险榜和高频售后问题 |
| 操作日志 | 统一检索 Agent、人工客服与飞书产生的关键业务流水，并跳转关联工单和 Run |
| Redis 增强 | 可选启用限流、Dashboard 缓存、RAG 缓存、会话上下文和风险榜 |

## 技术栈

**后端**：Python、FastAPI、SQLAlchemy、Pydantic、SQLite、pytest
**Agent / RAG**：LangGraph、LangChain、FAISS、可选 LLM Gateway
**前端**：Vite、React、TypeScript、Ant Design、Recharts、Vitest
**协同与缓存**：飞书 Webhook、Redis
**部署**：Docker、Docker Compose、Nginx

## 架构概览

```text
React 前端
  ├─ /workspace  Copilot 工作台
  ├─ /tickets    工单中心
  ├─ /runs       Agent 追踪与 Trace Waterfall
  ├─ /dashboard  运营看板
  └─ /operation-logs 操作日志

FastAPI 后端
  ├─ 业务 API：订单、物流、工单、事件、Dashboard
  ├─ Copilot API：同步分析、异步启动、SSE 实时事件
  ├─ LangGraph：意图识别 -> 订单提取 -> 订单/物流查询 -> 异常判断
  │             -> RAG 检索/重排序 -> 回复生成 -> 审核判断 -> 建单/复用 -> 飞书通知
  ├─ RAG：LangChain Document -> deterministic embedding -> FAISS -> rerank
  ├─ LLM Gateway：disabled / openai_compatible / ollama
  └─ 可观测性：agent_runs、agent_steps、ticket_events、feishu_events、operation_logs

SQLite
  ├─ orders / logistics
  ├─ tickets / ticket_events / feishu_events
  ├─ agent_runs / agent_steps
  ├─ session_ticket_bindings
  └─ operation_logs

Redis（可选）
  ├─ 令牌桶限流
  ├─ Dashboard 聚合缓存
  ├─ RAG 中间结果缓存
  ├─ 会话上下文
  └─ 运营风险榜
```

## 快速启动

### 方式一：本地开发启动

后端使用本机 `rag_910` 环境：

```bash
/opt/anaconda3/envs/rag_910/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8001 --reload
```

前端：

```bash
cd frontend
npm run dev
```

打开：

```text
http://127.0.0.1:5173/workspace
```

### 方式二：Docker Compose 启动

确保 Docker Desktop 已启动，在项目根目录运行：

```bash
docker compose up --build
```

后台运行：

```bash
docker compose up --build -d
```

查看日志：

```bash
docker compose logs -f
```

停止服务：

```bash
docker compose down
```

Compose 会启动两个服务：

| 服务 | 地址 | 说明 |
| --- | --- | --- |
| `copilot` | `http://127.0.0.1:8001` | FastAPI 后端 |
| `frontend` | `http://127.0.0.1:5173` | Nginx 托管的 React 前端 |

容器中的 SQLite 数据库挂载到本地 `./data/app.db`，重启容器不会丢失本地工单和 Agent Run。

## 环境变量

项目默认不调用真实模型、不发送真实飞书消息、不强依赖 Redis。需要启用外部能力时，在项目根目录创建 `.env`，可参考 [`.env.example`](.env.example)。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./data/app.db` | SQLite 数据库地址 |
| `LLM_PROVIDER` | `disabled` | 可选 `disabled`、`openai_compatible`、`ollama` |
| `LLM_BASE_URL` | 空 | OpenAI-compatible 或 Ollama 服务地址 |
| `LLM_API_KEY` | 空 | 模型服务密钥 |
| `LLM_MODEL` | 空 | 模型名称 |
| `FEISHU_WEBHOOK_URL` | 空 | 普通协同通知使用的飞书群自定义机器人 Webhook |
| `FEISHU_APP_ID` | 空 | 飞书自建应用 App ID，用于发送审核交互卡片 |
| `FEISHU_APP_SECRET` | 空 | 飞书自建应用 App Secret，只写入本地 `.env` |
| `FEISHU_CHAT_ID` | 空 | 自建应用机器人所在群的 `chat_id` |
| `FEISHU_CALLBACK_VERIFY_TOKEN` | 空 | 飞书回调校验 token，后续真实联调时启用 |
| `REDIS_URL` | 空 | 配置后启用 Redis 限流、缓存、会话和风险榜 |
| `COPILOT_RATE_LIMIT_CAPACITY` | `10` | Copilot 令牌桶容量 |
| `COPILOT_RATE_LIMIT_WINDOW_SECONDS` | `60` | 限流窗口 |
| `DASHBOARD_CACHE_TTL_SECONDS` | `60` | Dashboard 缓存 TTL |
| `RAG_CACHE_TTL_SECONDS` | `300` | RAG 中间结果缓存 TTL |
| `OPERATION_LOG_DIR` | `./logs` | 本地 JSONL 操作日志目录 |

### 接入 OpenAI-compatible 服务

```bash
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://your-llm-provider.example.com/v1
LLM_API_KEY=replace-with-your-key
LLM_MODEL=replace-with-your-model
```

### 接入 Ollama

```bash
LLM_PROVIDER=ollama
LLM_BASE_URL=http://127.0.0.1:11434
LLM_MODEL=qwen3:8b
```

真实模型只增强意图识别、订单号提取、RAG 查询改写和客服回复草稿。订单查询、物流查询、异常判断、建单、状态流转、审核边界和飞书通知仍由确定性业务代码控制。

### 飞书协同模式

项目将飞书拆成两条链路：普通物流异常工单继续通过 `FEISHU_WEBHOOK_URL` 发送群通知；退款、退货、补偿、重发、改地址、取消订单等需要人工审核的工单，通过飞书自建应用机器人发送 interactive 审核卡片。群自定义机器人 Webhook 不支持真实按钮回调，因此审核卡片需要配置 `FEISHU_APP_ID`、`FEISHU_APP_SECRET` 和 `FEISHU_CHAT_ID`。

## 访问入口

| 页面或接口 | 地址 |
| --- | --- |
| React Copilot 工作台 | `http://127.0.0.1:5173/workspace` |
| React 工单中心 | `http://127.0.0.1:5173/tickets` |
| React Agent 追踪 | `http://127.0.0.1:5173/runs` |
| React 运营看板 | `http://127.0.0.1:5173/dashboard` |
| React 操作日志 | `http://127.0.0.1:5173/operation-logs` |
| Swagger API 文档 | `http://127.0.0.1:8001/docs` |
| 健康检查 | `http://127.0.0.1:8001/health` |
| 服务端工单后台 | `http://127.0.0.1:8001/admin/tickets` |
| 服务端 Run 后台 | `http://127.0.0.1:8001/admin/runs` |
| 服务端运营看板 | `http://127.0.0.1:8001/admin/dashboard` |

## 演示数据

应用启动时会幂等写入 12 条本地演示订单，覆盖常见售后链路：

| 订单 | 场景 | 预期 |
| --- | --- | --- |
| `ORD-1001` | 订单未收到，物流异常 | 创建或复用催物流工单 |
| `ORD-1002` | 物流正常查询 | 不创建工单，生成查询回复 |
| `ORD-1003` | 物流停滞 96 小时 | 创建或复用催物流工单 |
| `ORD-1004` | 已付款未发货 | 召回发货时效规则，不误建物流工单 |
| `ORD-1005` | 显示签收但用户未收到 | 召回签收争议 SOP |
| `ORD-1006` | 高金额退款 | 创建待审核工单，优先级 high |
| `ORD-1007` | 低金额仅退款 | 创建待审核工单，优先级 medium |
| `ORD-1008` | 退货申请 | 进入人工审核 |
| `ORD-1009` | 换货申请 | 进入人工审核 |
| `ORD-1010` | 发货后改地址 | 进入人工审核 |
| `ORD-1011` | 取消订单 | 进入人工审核 |
| `ORD-1012` | 物流正常但催单 | 不创建物流工单 |

完整测试问题见 [docs/LOCAL_DEMO.md](docs/LOCAL_DEMO.md)。

如需清理历史工单和 Run，重置为干净演示库：

```bash
/opt/anaconda3/envs/rag_910/bin/python scripts/reset_demo_database.py
```

该脚本会清空当前 `DATABASE_URL` 指向的本地数据库，并重新写入演示订单和物流数据。

## 推荐体验路径

1. 打开 `http://127.0.0.1:5173/workspace`。
2. 输入物流异常问题：

   ```text
   我的订单 ORD-1001 怎么还没收到？帮我催一下物流。
   ```

3. 观察工作台中的实时 Agent Step、回复草稿、RAG 规则来源、工单结果和飞书状态。
4. 打开 `/tickets`，查看新建或复用的工单、审核状态、事件时间线和关联 Run。
5. 打开 `/runs`，进入 Run 详情，查看 Trace Waterfall 和 Step 输入输出摘要。
6. 打开 `/dashboard`，查看工单指标、Agent 性能、风险榜和高频售后问题。
7. 输入退款审核问题：

   ```text
   订单 ORD-1006 金额比较高，我想退款。
   ```

8. 使用 callback 模拟审核：

   ```bash
   curl -s -X POST http://127.0.0.1:8001/api/feishu/callback \
     -H 'Content-Type: application/json' \
     -d '{"event_id":"FEISHU-DEMO-APPROVE-001","ticket_id":"替换成待审核工单ID","action":"approve","operator":"主管A"}'
   ```

## RAG 设计

当前 RAG 链路为：

```text
用户问题
-> query_rewrite
-> FAISS 候选召回
-> deterministic rerank
-> policy_sources
-> 回复草稿
```

知识库位于 [memory/policy_knowledge.py](memory/policy_knowledge.py)，当前以「一条 SOP / 一条规则 / 一段话术 = 一个 Document」作为检索单元，覆盖物流异常、正常催单、未发货、签收争议、退款、仅退款、退货、换货、改地址、取消订单、补偿赔付、投诉升级和运费规则。

当前 embedding 由 [services/policy_service.py](services/policy_service.py) 中的 `DeterministicPolicyEmbedding` 提供：它实现 LangChain `Embeddings` 接口，通过售后关键词计数生成可重复向量，再交给 FAISS 建索引。这样可以在没有外部模型和网络依赖的情况下保证自动化测试稳定。后续知识库规模上来后，可以替换为真实 embedding 模型、Milvus / pgvector / Qdrant，以及独立 reranker。

## Agent 可观测性

每次 Copilot 分析都会生成一条 `agent_runs` 和多条 `agent_steps`：

```text
intent_recognition
-> order_extract
-> order_query
-> session_binding_check
-> follow_up_check
-> logistics_query
-> abnormal_check
-> query_rewrite
-> policy_retrieval
-> policy_rerank
-> reply_generate
-> approval_check
-> ticket_create
-> feishu_notify
```

Run 详情页会展示：

- Step 状态、类型和耗时
- 输入摘要、输出摘要和错误信息
- LLM provider、model、token 和 fallback reason
- RAG 缓存命中状态
- Trace Waterfall 连续比例条

## 操作日志与审计

`ticket_events` 记录单张工单的状态时间线，`feishu_events` 记录飞书回调，`agent_steps` 记录单次 Agent 执行步骤。`operation_logs` 则提供跨对象的统一操作流水，用于检索 Copilot 分析、自动建单/复用、人工操作和飞书审核。

前端可在 `/operation-logs` 按操作人、动作、工单 ID、Run ID、订单 ID 和状态筛选。数据库用于页面查询；本地同时写入按日期拆分的 JSONL 文件：

```text
logs/operation-YYYY-MM-DD.jsonl
```

文件日志只保留结构化业务摘要和关联 ID，不写入 API Key、App Secret、Webhook URL 或完整飞书回调内容。

## 主要 API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/health` | 服务健康检查 |
| `GET` | `/api/orders/{order_id}` | 查询订单 |
| `GET` | `/api/logistics/{order_id}` | 查询物流 |
| `POST` | `/api/tickets` | 创建工单 |
| `GET` | `/api/tickets` | 查询工单列表 |
| `GET` | `/api/tickets/{ticket_id}` | 查询工单详情 |
| `POST` | `/api/tickets/{ticket_id}/actions` | 工单人工状态操作 |
| `POST` | `/api/copilot/analyze` | 同步执行 Copilot 分析 |
| `POST` | `/api/copilot/analyze/start` | 异步启动 Copilot 分析 |
| `GET` | `/api/runs` | 查询 Run 列表 |
| `GET` | `/api/runs/{run_id}` | 查询 Run 详情 |
| `GET` | `/api/runs/{run_id}/steps` | 查询 Step 链路 |
| `GET` | `/api/runs/{run_id}/events` | SSE 实时事件流 |
| `GET` | `/api/operation-logs` | 查询全局操作日志，可按关联 ID 等字段筛选 |
| `POST` | `/api/feishu/callback` | 模拟飞书卡片回调 |
| `GET` | `/api/dashboard/overview` | 查询运营概览 |
| `GET` | `/api/dashboard/ticket-stats` | 查询工单统计 |
| `GET` | `/api/dashboard/agent-performance` | 查询 Agent 性能 |
| `GET` | `/api/dashboard/risk-ranking` | 查询运营风险榜 |

完整参数和响应结构见 Swagger：`http://127.0.0.1:8001/docs`。

## 测试与验证

后端测试：

```bash
/opt/anaconda3/envs/rag_910/bin/python -m pytest -q
```

前端测试：

```bash
cd frontend
npm run test:run
npm run build
```

Docker Compose 配置检查：

```bash
docker compose config --quiet
```

测试覆盖健康检查、订单与物流 API、工单状态机、Copilot LangGraph 工作流、RAG 检索与重排序、飞书通知与回调、SSE 实时事件、操作日志数据库/JSONL 与筛选 API、Dashboard API、React 页面渲染和 Trace Waterfall 交互。

## 项目文档

- [协作规则](AGENTS.md)
- [产品与技术规划](ecommerce_after_sales_copilot_plan.md)
- [当前实施状态](docs/STATUS.md)
- [本地演示用例](docs/LOCAL_DEMO.md)
- [项目展示脚本](docs/DEMO_SCRIPT.md)
- [项目展示材料](docs/PROJECT_SHOWCASE.md)

## 当前边界

- 当前订单、物流和售后规则均为本地演示数据，未接入真实电商平台。
- 默认不调用真实 LLM、真实飞书或付费 embedding API。
- 飞书真实卡片按钮点击依赖公网 HTTPS callback，并需要通过自建应用机器人发送审核卡片；Webhook 只承担普通通知。
- 当前 RAG 使用人工整理的短规则 Document，尚未实现长文档解析、chunk overlap、父子 chunk 和增量入库。
- SQLite 适合本地演示和单机开发，生产化可迁移至 PostgreSQL。
- RabbitMQ 可靠投递后置到真实飞书回调跑通之后，用于通知失败重试、长耗时任务重试和失败告警。

## 后续演进

```text
本地全链路验收
-> Docker Compose 与展示材料收口
-> Cloudflare Tunnel / 域名公网访问
-> 真实飞书卡片回调联调
-> RabbitMQ 可靠投递
-> 真实电商平台 / 多租户 / 权限体系
-> 真实 embedding、向量数据库和 reranker
```
