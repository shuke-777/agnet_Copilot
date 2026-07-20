# 项目展示材料

本文档用于整理电商售后客服 Copilot 的展示结构、核心亮点和技术说明。README 负责项目总览与启动方式，本文档更侧重系统设计、业务价值和可展示链路。

## 一句话定位

这是一个面向电商售后客服团队的 Copilot 工单系统，用 Agent 编排订单查询、物流判断、售后规则检索、客服回复草稿、工单协同、人工审核和执行链路追踪，实现可人工接管的半自动化售后处理闭环。

## 背景与价值

电商售后客服中，「订单未收到」「物流异常」「退款」「退货」「改地址」「取消订单」等问题频率高，但处理过程通常需要客服在多个系统之间切换：

- 查询订单与物流状态
- 判断是否达到异常或审核标准
- 查找售后 SOP 与客服话术
- 创建工单并同步协作群
- 等待人工审核或主管确认
- 记录处理动作，便于后续追责和复盘

本项目将这些动作拆分为明确的业务模块和 Agent Step，让 Copilot 负责识别、查询、判断和建议，同时保留人工审核与状态推进。系统重点不是让 Agent 自动做所有决定，而是让售后处理过程可追踪、可测试、可解释、可接管。

## 核心闭环

```text
用户售后问题
-> Copilot 实时分析
-> 意图识别与订单号提取
-> 查询订单与物流
-> 判断物流异常 / 审核风险
-> RAG 检索售后规则和客服话术
-> 生成回复草稿
-> 创建或复用工单
-> 飞书通知或人工审核
-> 工单状态流转与事件审计
-> Agent Trace / Dashboard 复盘
```

## 主要场景

| 场景 | Copilot 处理结果 |
| --- | --- |
| 订单未收到，物流超过 72 小时未更新 | 创建或复用催物流工单，生成安抚回复，通知协同群 |
| 物流正常但用户催单 | 返回物流查询回复，不创建工单 |
| 已付款未发货 | 召回发货时效 SOP，不误判为物流异常 |
| 显示签收但用户未收到 | 召回签收争议 SOP，引导核实代收信息 |
| 高金额退款 | 创建待审核工单，Agent 只给建议，不直接执行退款 |
| 退货、换货、改地址、取消订单、补偿 | 进入人工审核，记录审核原因和建议动作 |

## 技术架构

```text
Frontend
  Vite + React + TypeScript + Ant Design + Recharts
  ├─ Copilot 工作台
  ├─ 工单中心
  ├─ Agent 追踪
  └─ 运营看板

Backend
  FastAPI + SQLAlchemy + Pydantic
  ├─ REST API
  ├─ SSE 实时事件
  ├─ LangGraph Agent Workflow
  ├─ LLM Gateway
  ├─ RAG Policy Service
  ├─ Ticket / Event Services
  └─ Feishu Webhook / Callback Services

Data
  SQLite
  ├─ orders / logistics
  ├─ tickets / ticket_events
  ├─ agent_runs / agent_steps
  ├─ feishu_events
  └─ session_ticket_bindings

Optional Infra
  Redis
  ├─ rate limit
  ├─ dashboard cache
  ├─ RAG cache
  ├─ session context
  └─ risk ranking
```

## LangGraph 编排

当前工作流按业务步骤拆分，便于测试和观测：

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

设计重点：

- 查询订单、物流、工单状态流转等关键动作由确定性代码执行。
- LLM 只增强意图识别、订单号提取、RAG 查询改写和回复草稿。
- LLM 调用失败、超时或返回结构不合格时，自动降级到确定性逻辑。
- 每个 Step 都写入 `agent_steps`，用于前端 Trace Waterfall 和后续性能分析。

## RAG 设计

RAG 在本项目中承担「售后规则依据」和「客服话术来源」的角色，不直接决定高风险业务动作。

当前链路：

```text
用户问题 + 业务上下文
-> query_rewrite
-> FAISS 候选召回
-> deterministic rerank
-> policy_sources
-> 回复草稿
```

当前知识库特点：

- 使用本地 `Document` 管理售后 SOP、审核规则和话术。
- 一条 SOP / 一条规则 / 一段话术作为一个检索单元。
- 使用 LangChain `Embeddings` 接口封装 deterministic embedding。
- 使用 FAISS 完成候选召回。
- 使用意图、物流异常状态和关键词相关度做二次排序。

后续可替换为：

- 真实 embedding 模型
- Milvus / pgvector / Qdrant
- 长文档解析与 chunk overlap
- 父子 chunk
- reranker
- 知识库版本管理和增量入库

## 人工审核边界

Agent 不直接执行退款、补偿、重发、改地址、取消订单等高风险动作。

审核判断规则：

| 动作类型 | 是否需要审核 |
| --- | --- |
| 物流查询 / 催物流 | 不需要审核 |
| 退款 / 仅退款 | 需要审核 |
| 退货 / 换货 | 需要审核 |
| 改地址 / 取消订单 | 需要审核 |
| 补偿 / 赔付 / 优惠券 | 需要审核 |
| 高金额订单 | 提升优先级 |

审核状态：

```text
not_required
pending
approved
rejected
manual_confirm
```

本地阶段通过 `POST /api/feishu/callback` 模拟飞书卡片按钮；公网 HTTPS callback 和真实飞书事件 payload 适配放到部署阶段完成。

## Agent Trace 与可观测性

系统记录两层可观测数据：

| 表 | 作用 |
| --- | --- |
| `agent_runs` | 记录一次 Copilot 分析的输入、状态、意图、订单、工单、总耗时和最终结果 |
| `agent_steps` | 记录每个 Agent Step 的类型、状态、耗时、输入摘要、输出摘要、错误、LLM 元数据和缓存命中 |

前端 Run 详情页提供：

- 连续比例条式 Trace Waterfall
- Step 图例和点击详情
- LLM provider / model / token / fallback reason
- RAG 缓存命中标记
- 工单 ID 与 Run ID 对齐

这让系统不仅能返回结果，还能解释每一步为什么这样处理。

## Redis 增强

Redis 是可选增强，不影响基础链路。

| 能力 | 说明 |
| --- | --- |
| Copilot 限流 | 使用令牌桶保护分析接口 |
| Dashboard 缓存 | 缓存聚合指标，状态变化后主动失效 |
| RAG 缓存 | 缓存 query rewrite、retrieval、rerank 中间结果 |
| 会话上下文 | 保存短期多轮咨询上下文和最近订单号 |
| 运营风险榜 | 使用 Sorted Set 维护承运商异常、高优先级工单和高频问题 |

Redis 不可用时，系统自动降级到 SQLite 实时查询或直接放行。

## 推荐展示路径

1. 打开 Copilot 工作台，输入 `ORD-1001` 物流异常问题。
2. 展示实时 Agent Step、RAG 来源、回复草稿和催物流工单。
3. 输入 `ORD-1002` 正常物流问题，展示不误建单。
4. 输入 `ORD-1006` 高金额退款问题，展示人工审核。
5. 打开工单中心，查看工单详情、审核状态和事件时间线。
6. 打开 Agent 追踪，查看 Trace Waterfall。
7. 打开运营看板，查看工单指标、Agent 性能和风险榜。
8. 使用本地 callback 模拟审核通过或拒绝。

## 项目亮点总结

- 将 Agent 从「问答」落到「售后工单处理」业务闭环。
- 用 LangGraph 将复杂流程拆成可测试、可观测的节点。
- 用 RAG 提供售后规则来源，增强回复可信度。
- 用确定性业务逻辑约束高风险动作，避免 Agent 越权执行。
- 用 Run / Step / Ticket Event / Feishu Event 做完整链路审计。
- 用 SSE 和 Trace Waterfall 让前端实时展示 Agent 执行过程。
- 用 Redis 做限流、缓存、会话和风险榜，同时保持可降级。
- 用 Docker Compose 提供前后端一体化本地启动方式。

## 当前边界与演进

当前阶段已经完成本地业务闭环和展示材料收口。后续演进顺序：

```text
Cloudflare Tunnel / 域名公网访问
-> 真实飞书卡片回调联调
-> RabbitMQ 可靠投递
-> 真实电商平台接口
-> PostgreSQL / 多租户 / 权限体系
-> 真实 embedding、向量数据库和 reranker
```
