# M15 本地全链路演示脚本

本脚本用于 5-8 分钟面试或项目展示。目标不是把所有边界都讲完，而是把“客服 Copilot 如何完成售后闭环”讲清楚。

## 展示目标

```text
用户售后问题
-> Copilot 实时分析
-> 查订单 / 查物流
-> RAG 召回售后规则
-> 生成回复草稿
-> 自动创建或复用工单
-> 人工审核 / 飞书模拟回调
-> Agent Trace 和 Dashboard 可追踪
```

## 启动

后端：

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

## 演示顺序

### 1. 先讲项目定位

一句话：

```text
这是一个电商售后客服 Copilot，不是普通聊天机器人；它把订单查询、物流判断、售后规则检索、回复生成、工单协同和 Agent 执行追踪串成一个可人工接管的闭环。
```

重点强调：

- Agent 负责识别、查询、判断和建议。
- 人工负责审核、确认和推进状态。
- 系统负责记录 run、step、工单事件和飞书回调。

### 2. 演示物流异常自动建单

在 `/workspace` 输入：

```text
我的订单 ORD-1001 怎么还没收到？帮我催一下物流。
```

预期展示：

- 识别订单 `ORD-1001`。
- 判断物流异常。
- RAG 召回 72 小时未更新 SOP 和催物流标准。
- 生成客服回复草稿。
- 创建或复用催物流工单。
- 实时 Agent Step 持续出现。

讲解重点：

```text
这里体现的是最核心 MVP：订单未收到 -> 物流异常判断 -> 自动生成催物流工单。
```

### 3. 演示正常物流不误建单

点击“新建咨询”，输入：

```text
帮我看一下订单 ORD-1002 的物流。
```

预期展示：

- 识别订单 `ORD-1002`。
- 判断物流正常。
- 生成安抚和查询回复。
- 不创建工单。

讲解重点：

```text
系统不是所有问题都建单，而是根据业务状态决定是否需要后续处理。
```

### 4. 演示退款进入人工审核

点击“新建咨询”，输入：

```text
订单 ORD-1006 金额比较高，我想退款。
```

预期展示：

- RAG 召回高金额退款审核规则。
- `approval_required = true`。
- 生成待审核工单。
- 工单优先级为 high。
- Agent 不直接执行退款。

讲解重点：

```text
高风险动作由 Agent 给出建议，但必须进入人工审核，不会自动退款或自动补偿。
```

### 5. 查看工单中心

打开：

```text
http://127.0.0.1:5173/tickets
```

预期展示：

- 能看到物流催办工单和退款审核工单。
- 工单中心支持按 `TCK-`、`RUN-`、`ORD-` 检索。
- 工单详情展示审核状态、审核原因、事件时间线和关联 Run。

讲解重点：

```text
客服可以从业务工单视角接管 Agent 的建议，所有状态变化都会留下事件记录。
```

### 6. 模拟飞书审核回调

复制退款审核工单 ID，用本地 callback 模拟主管点击“通过”：

```bash
curl -s -X POST http://127.0.0.1:8001/api/feishu/callback \
  -H 'Content-Type: application/json' \
  -d '{"event_id":"FEISHU-DEMO-APPROVE-001","ticket_id":"替换成待审核工单ID","action":"approve","operator":"主管A"}'
```

可换成：

```text
reject
manual_confirm
```

预期展示：

- 工单审核状态更新。
- `ticket_events` 记录业务事件。
- `feishu_events` 记录外部回调事件。

讲解重点：

```text
当前本地用 callback 模拟飞书按钮，真实飞书公网回调会放到 Cloudflare Tunnel / 服务器部署之后联调。
```

### 7. 查看 Agent Trace

打开：

```text
http://127.0.0.1:5173/runs
```

进入刚才的 Run 详情。

预期展示：

- 工单 ID 和 Run ID 可对齐。
- Trace Waterfall 展示各 step 耗时占比。
- 能看到 RAG、LLM Gateway、建单、飞书通知等 step 输入输出摘要。

讲解重点：

```text
这个项目的亮点是 Agent 可观测，不只是返回一个答案，而是能追踪每一步为什么这么判断。
```

### 8. 查看 Dashboard

打开：

```text
http://127.0.0.1:5173/dashboard
```

预期展示：

- 工单总量、待处理、高优先级等指标变化。
- Agent 成功率和 Step 性能指标。
- 风险榜展示异常物流、待处理高优先级工单和高频售后问题。

讲解重点：

```text
客服主管可以从运营视角看积压、风险和 Agent 性能，而不是只看单条对话。
```

## 推荐补充用例

如果时间充足，可继续演示：

| 场景 | 输入 |
| --- | --- |
| 物流停滞 96 小时 | `订单 ORD-1003 物流 96 小时没更新，帮我催一下物流。` |
| 未发货咨询 | `订单 ORD-1004 已经付款了，什么时候发货？` |
| 签收争议 | `订单 ORD-1005 显示签收了，但我没收到。` |
| 低金额仅退款 | `订单 ORD-1007 我想仅退款。` |
| 改地址审核 | `订单 ORD-1010 已经发货了，我想改地址。` |

完整 12 条用例见 [`docs/LOCAL_DEMO.md`](LOCAL_DEMO.md)。

## 收尾讲法

```text
当前阶段已经完成本地闭环：前端工作台、业务 API、LangGraph 编排、RAG 规则检索、工单状态流转、人工审核模拟、Agent Trace 和 Dashboard。

后续会先做 Docker Compose / README / 展示材料收口，然后通过 Cloudflare Tunnel 或服务器部署暴露 HTTPS callback，最后接入真实飞书卡片回调。RabbitMQ 会放在真实飞书之后，用于通知重试、长耗时任务重试和失败告警。
```

## 验收命令

```bash
/opt/anaconda3/envs/rag_910/bin/python -m pytest -q
```

```bash
cd frontend
npm run test:run
npm run build
```
