# M10.8 会话主工单绑定设计

## 背景与目标

M10.7 已能按 `order_id + ticket_type + 未关闭状态` 复用工单，但连续咨询仍缺少持久的会话主工单关系。Redis 只保存短期消息，不能作为业务关联的事实来源；普通物流追问也不会自动关联已经创建的工单。

M10.8 使用 SQLite 持久保存会话、用户作用域、订单与主工单的关系，并把“识别物流问题”和“用户明确要求催办”拆成两个信号。完成后应满足：

- 同一会话、同一用户、同一订单的物流追问关联同一个活动工单。
- 重复提交或连续追问不重复建单、不重复发送飞书新建通知。
- 同一会话切换订单时明确拒绝，避免新订单污染旧工单。
- 退款、退货、运费和发货时效咨询不自动关联物流工单。
- Redis 不可用时，持久关联和冲突判断仍然生效。

## 数据模型与服务边界

新增 `session_ticket_bindings` 表：

| 字段 | 约束 | 含义 |
| --- | --- | --- |
| `binding_id` | 主键，`STB-*` | 关联记录 ID |
| `session_id` | 非空、索引 | Copilot 会话 ID |
| `user_scope` | 非空、索引 | `user_id`；缺失时使用内部常量 `__anonymous__` |
| `order_id` | 非空、外键、索引 | 会话锁定的订单 |
| `ticket_id` | 非空、外键、索引 | 当前或最近一次主工单 |
| `created_at` | 非空 | 首次绑定时间 |
| `updated_at` | 非空 | 主工单更新或重新绑定时间 |

数据库对 `(session_id, user_scope)` 建唯一约束，保证一个用户作用域内的一个会话只能锁定一个订单。`order_id` 不随工单关闭而改变；用户需要处理另一订单时必须创建新会话。绑定的工单解决后保留历史关系，但只有 `todo` 或 `processing` 工单属于活动主工单。

新增专用 `SessionTicketBindingService`，负责：

- 将可空 `user_id` 归一化为稳定的 `user_scope`。
- 查询会话绑定并校验订单一致性。
- 读取同订单的活动主工单。
- 在创建或复用工单后幂等创建/更新绑定。
- 在同订单重新产生新活动工单时更新 `ticket_id`，保留原始 `created_at` 并刷新 `updated_at`。

模型与服务不依赖 Redis。现有启动迁移继续采用增量方式：新表由 `Base.metadata.create_all` 创建，不删除或重建现有 SQLite 表。

## 工作流与业务规则

### 订单一致性

在 `order_query` 成功后、`logistics_query` 前新增 `session_binding_check` 规则节点：

1. 没有绑定时继续工作流。
2. 绑定订单等于本轮订单时，将活动主工单放入工作流状态；已解决工单只保留历史信息，不作为活动工单。
3. 绑定订单与本轮订单不一致时，记录失败 Step，并抛出 HTTP 409。

没有冲突时也记录 `success` Step，输出分别为“无会话绑定”“存在同订单活动工单”或“同订单绑定的工单已非活动状态”，保证 Trace 中始终可见本轮一致性判断。

冲突发生后不执行物流查询、RAG、建单和飞书通知。Agent Run 标记为 `failed`，Redis 会话上下文不追加本轮内容，Dashboard 缓存按现有失败流程失效。

订单号的数据库历史回退只读取 `status=success` 的既有 Run。这样失败的跨订单请求不会成为下一轮缺失订单号时的候选上下文。

### 明确催办信号

在 `abnormal_check` 后新增 `follow_up_check` 规则节点，并在 `CopilotState` 增加 `follow_up_requested: bool`。该节点只根据本轮用户消息判断，不从历史消息继承催办意愿，并记录一个可观测 Step。

消息包含以下任一固定短语时视为明确催办：“催一下”“催物流”“催快递”“继续催”“继续跟进”“帮我跟进”“帮我催”“加急”“尽快处理”“联系快递”“联系物流”。单独出现“没收到”“未收到”“物流异常”“查物流”不视为明确催办。匹配使用确定性的子串判断，不调用 LLM，也不扩展近义词。

`follow_up_check` 每次执行都记录 `success` Step，输出为 `requested` 或 `not_requested`。

“催发货”“什么时候发货”“还没发货”继续归类为 `shipping_timeliness`，不会创建催物流工单。

### 工单决策

`ticket_create_node` 按以下优先级决策：

1. 当前意图不是 `logistics_delay` 时返回 `none`，不关联物流工单。
2. 会话已有同订单活动主工单时，将当前 Run 关联该工单，返回 `session_linked`；不要求再次明确催办，不新增 `copilot_followup_analyzed` 事件，也不发送飞书新建通知。
3. 没有会话活动主工单时，只有订单状态为 `shipped`、物流异常且 `follow_up_requested=true` 才进入建单逻辑；否则返回 `none`。
4. 全局存在同订单、同类型的 `todo/processing` 工单时复用，写入 `copilot_followup_analyzed` 事件，返回 `reused`，并建立会话绑定。
5. 不存在活动工单时创建催物流工单，返回 `created`，并建立会话绑定。

`created`、`reused` 和 `session_linked` 都把 `agent_runs.ticket_id` 指向主工单。只有 `created` 允许飞书新建通知；其余结果均由现有飞书节点记录 `skipped` Step。

工单从 `resolved` 重新打开为 `processing` 后，既有绑定再次成为活动绑定。同订单在旧工单保持 `resolved` 时重新明确催办，则创建新的工单并把绑定更新到新工单。

## API 与前端契约

`POST /api/copilot/analyze` 的成功响应新增：

```json
{
  "ticket_association": "created"
}
```

允许值为 `created | reused | session_linked | none`。现有 `ticket_created` 和 `ticket_reused` 字段在 M10.8 保留：仅对应结果为 `created` 或 `reused` 时为 `true`，避免破坏现有调用方。

跨订单请求返回 HTTP 409：

```json
{
  "detail": {
    "code": "session_order_mismatch",
    "bound_order_id": "ORD-1001",
    "requested_order_id": "ORD-1002"
  }
}
```

前端识别该错误后：

- 显示当前会话绑定订单和本轮识别订单。
- 提供现有“新建咨询”命令作为主要操作。
- 保留用户当前输入，不把失败请求追加到本地消息列表。
- 用户点击“新建咨询”后只重置会话、消息和结果，保留输入草稿，便于重新提交。

工作台根据 `ticket_association` 分别显示“已创建”“已复用”“已关联会话工单”或“未关联工单”，不再从两个布尔字段推导完整状态。

## 错误处理与一致性

- 会话冲突是业务冲突，使用 409，不创建或修改绑定。
- 绑定写入、工单创建或复用、Run 关联、工单事件和本轮 `ticket_create` Step 在同一个数据库事务内提交；业务对象先 `flush`，由 Step 记录统一提交，任一步失败时整体回滚。
- 唯一约束冲突时重新读取绑定；若订单一致则按幂等成功处理，若订单不一致则返回 409。
- 找不到绑定指向的工单属于数据一致性错误，记录失败 Step 并使 Run 失败，不静默创建新工单。
- Redis 读取失败继续按现有方式降级，但不能绕过 SQLite 会话订单检查。
- 不新增真实电商平台、飞书凭据、认证体系、租户模型或 RabbitMQ 依赖。

## 测试与验收

后端自动化测试覆盖：

- 首次明确催办创建工单和绑定，返回 `created`。
- 同会话同订单普通物流追问返回 `session_linked`，Run 关联原工单且不重复写事件或发飞书。
- 新会话对同订单明确催办复用全局活动工单，返回 `reused` 并创建自己的绑定。
- 没有明确催办的“没收到”只生成回复，返回 `none`。
- 订单未发货、物流正常或非物流意图均不建催物流工单。
- 同会话切换订单返回 409，后续节点不执行，Run 失败且绑定不变。
- 不同 `user_id` 使用相同 `session_id` 时彼此隔离。
- 缺失 `user_id` 的请求在匿名作用域内保持稳定绑定。
- 已解决工单不自动关联；同订单再次明确催办创建新工单并更新绑定。
- 已解决工单重新打开后重新成为活动主工单。
- 失败的跨订单 Run 不参与后续订单号历史回退。
- 并发或重复提交不会产生同一会话的重复绑定。

前端测试覆盖：

- 四种成功关联状态的文案。
- 409 冲突提示展示两个订单号和“新建咨询”操作。
- 冲突后输入不丢失、消息列表不追加。
- 新建咨询生成新 `session_id`，保留冲突时的输入草稿。

手工验收使用 Swagger 或 React 工作台依次执行：首次催办、同订单追问、跨订单冲突、新建咨询后重新提交，并在工单详情与 Agent Trace 中核对工单、Run、Step 和飞书跳过记录。

完成前运行：

```bash
/opt/anaconda3/envs/rag_910/bin/python -m pytest -q
cd frontend && npm run test:run
cd frontend && npm run build
docker compose config --quiet
```

M10.8 不包含 Redis Sorted Set 风险榜、RabbitMQ、实时事件推送、真实认证或多租户隔离；这些继续留在后续里程碑。
