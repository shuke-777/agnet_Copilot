# M10.8 会话主工单绑定实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 用 SQLite 持久绑定 Copilot 会话、用户作用域、订单与活动主工单，区分物流识别与明确催办，并为跨订单会话返回可操作的 HTTP 409。

**架构：** 新增独立的 `SessionTicketBinding` 模型和服务作为业务事实来源，工作流在订单查询后校验绑定、在异常判断后识别本轮催办信号。建单节点用 `ticket_association` 统一表达创建、全局复用、会话关联和未关联四种结果；前端直接消费该字段，并把 409 作为保留草稿的业务冲突展示。

**技术栈：** Python 3.11、FastAPI、SQLAlchemy 2.x、LangGraph、SQLite、Pytest/unittest、React 18、TypeScript、Ant Design、Vitest/Testing Library

---

## 文件结构

- 创建 `services/session_ticket_binding_service.py`：归一化用户作用域、读取/校验绑定、解析活动主工单、幂等写入绑定。
- 创建 `agents/nodes/session_binding_check_node.py`：在物流查询前记录会话订单一致性 Step，并在冲突时抛出 409。
- 创建 `agents/nodes/follow_up_check_node.py`：确定性识别本轮明确催办短语并记录 Step。
- 创建 `tests/test_session_ticket_binding_service.py`：覆盖服务层用户隔离、匿名作用域、绑定更新和数据一致性。
- 修改 `models/business.py`：定义 `SessionTicketBinding` 表、唯一约束和关系。
- 修改 `services/bootstrap.py`：让新表随现有增量启动流程创建并加载模型元数据。
- 修改 `agents/state.py`：增加活动会话工单、催办信号和统一关联结果。
- 修改 `agents/workflow.py`：按规格插入两个新节点。
- 修改 `agents/nodes/order_extract_node.py`：数据库历史回退只使用成功 Run，并按用户作用域隔离。
- 修改 `agents/nodes/ticket_create_node.py`：实现 `none/session_linked/reused/created` 决策和绑定写入。
- 修改 `agents/nodes/feishu_notify_node.py`：为会话关联和全局复用输出准确的跳过原因。
- 修改 `schemas/copilot.py`：向成功响应添加 `ticket_association` 字段。
- 修改 `services/copilot_service.py`：返回统一关联结果，并确保冲突失败 Run 保留有效 Trace、不写 Redis。
- 修改 `tests/test_copilot_workflow.py`：覆盖节点顺序、显式催办、会话关联、工单关闭/重开和历史回退。
- 修改 `tests/test_copilot_analyze_api.py`：覆盖成功关联契约、409、用户隔离、匿名作用域和副作用。
- 修改 `frontend/src/services/api.ts`：声明关联枚举和 409 detail 类型。
- 修改 `frontend/src/CopilotAnalysisContext.tsx`：结构化保存冲突、失败时保留草稿、新建咨询时保留冲突草稿。
- 修改 `frontend/src/App.tsx`：显示四种关联文案和带“新建咨询”操作的冲突提示。
- 修改 `frontend/src/App.test.tsx`：覆盖四种文案、冲突不追加消息、草稿与新会话行为。
- 修改 `docs/STATUS.md`：全部验证通过后记录 M10.8 完成情况和 M10.6 下一步。

### 任务 1：持久绑定模型与服务

**文件：**
- 创建：`services/session_ticket_binding_service.py`
- 创建：`tests/test_session_ticket_binding_service.py`
- 修改：`models/business.py`
- 修改：`services/bootstrap.py`

- [ ] **步骤 1：编写模型与服务失败测试**

在 `tests/test_session_ticket_binding_service.py` 使用真实测试数据库覆盖以下接口：

```python
def test_bind_ticket_creates_stable_anonymous_binding(self) -> None:
    binding = self.service.bind_ticket(
        session_id="SESSION-ANON",
        user_id=None,
        order_id="ORD-1001",
        ticket_id=self.ticket.ticket_id,
    )
    self.assertEqual(binding.user_scope, "__anonymous__")
    self.assertEqual(self.service.get_binding("SESSION-ANON", None).ticket_id, self.ticket.ticket_id)

def test_get_active_ticket_isolated_by_user_scope(self) -> None:
    self.service.bind_ticket("SESSION-SHARED", "USER-001", "ORD-1001", self.ticket.ticket_id)
    self.assertIsNone(self.service.get_binding("SESSION-SHARED", "USER-002"))

def test_bind_ticket_updates_resolved_binding_for_same_order(self) -> None:
    original = self.service.bind_ticket("SESSION-1", "USER-001", "ORD-1001", self.ticket.ticket_id)
    replacement = self.make_ticket(status="todo")
    updated = self.service.bind_ticket("SESSION-1", "USER-001", "ORD-1001", replacement.ticket_id)
    self.assertEqual(updated.created_at, original.created_at)
    self.assertEqual(updated.ticket_id, replacement.ticket_id)

def test_get_active_ticket_rejects_missing_bound_ticket(self) -> None:
    self.service.bind_ticket("SESSION-1", "USER-001", "ORD-1001", "TCK-MISSING")
    with self.assertRaises(SessionBindingDataError):
        self.service.get_active_ticket("SESSION-1", "USER-001")
```

- [ ] **步骤 2：运行测试并确认因模型/服务缺失而失败**

运行：`/opt/anaconda3/envs/rag_910/bin/python -m pytest tests/test_session_ticket_binding_service.py -q`

预期：FAIL，导入 `SessionTicketBinding` 或 `SessionTicketBindingService` 失败。

- [ ] **步骤 3：实现模型和服务的最小接口**

模型使用唯一约束锁定 `(session_id, user_scope)`：

```python
class SessionTicketBinding(Base):
    __tablename__ = "session_ticket_bindings"
    __table_args__ = (
        UniqueConstraint("session_id", "user_scope", name="uq_session_ticket_binding_scope"),
    )

    binding_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    user_scope: Mapped[str] = mapped_column(String(64), index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.order_id"), index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.ticket_id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
```

服务公开稳定接口，并只把 `todo/processing` 视为活动工单：

```python
ANONYMOUS_USER_SCOPE = "__anonymous__"
ACTIVE_TICKET_STATUSES = ("todo", "processing")

class SessionTicketBindingService:
    def __init__(self, db: Session) -> None: ...
    @staticmethod
    def normalize_user_scope(user_id: str | None) -> str: ...
    def get_binding(self, session_id: str, user_id: str | None) -> SessionTicketBinding | None: ...
    def get_active_ticket(self, session_id: str, user_id: str | None) -> Ticket | None: ...
    def bind_ticket(self, session_id: str, user_id: str | None, order_id: str, ticket_id: str) -> SessionTicketBinding: ...
```

`bind_ticket` 对同订单更新 `ticket_id/updated_at`，对不同订单抛出 `SessionOrderMismatchError`；捕获 `IntegrityError` 时回滚后重读唯一键，订单一致则幂等返回，否则抛出同一冲突。

- [ ] **步骤 4：运行服务测试与数据库回归测试**

运行：`/opt/anaconda3/envs/rag_910/bin/python -m pytest tests/test_session_ticket_binding_service.py tests/test_database_config.py -q`

预期：全部 PASS，新表可由 `Base.metadata.create_all` 创建，现有迁移测试不回归。

- [ ] **步骤 5：提交任务 1**

```bash
git add models/business.py services/bootstrap.py services/session_ticket_binding_service.py tests/test_session_ticket_binding_service.py
git commit -m "feat: add persistent session ticket bindings"
```

### 任务 2：工作流校验、催办信号与工单决策

**文件：**
- 创建：`agents/nodes/session_binding_check_node.py`
- 创建：`agents/nodes/follow_up_check_node.py`
- 修改：`agents/state.py`
- 修改：`agents/workflow.py`
- 修改：`agents/nodes/order_extract_node.py`
- 修改：`agents/nodes/ticket_create_node.py`
- 修改：`agents/nodes/feishu_notify_node.py`
- 修改：`tests/test_copilot_workflow.py`

- [ ] **步骤 1：更新工作流测试，先表达新行为**

把原有异常物流样例改为明确催办，并新增：

```python
def test_abnormal_logistics_without_explicit_follow_up_does_not_create_ticket(self) -> None:
    state = self.run_workflow("订单 ORD-1001 一直没收到。", session_id="SESSION-NO-FOLLOWUP")
    self.assertEqual(state.ticket_association, "none")
    self.assertFalse(state.follow_up_requested)
    self.assertIsNone(state.ticket_id)

def test_same_session_followup_links_ticket_without_duplicate_event(self) -> None:
    first = self.run_workflow("订单 ORD-1001 没收到，帮我催一下物流。", session_id="SESSION-LINK")
    second = self.run_workflow("现在进展怎么样？", session_id="SESSION-LINK")
    self.assertEqual(first.ticket_association, "created")
    self.assertEqual(second.ticket_association, "session_linked")
    self.assertEqual(second.ticket_id, first.ticket_id)
    self.assertEqual(self.followup_event_count(first.ticket_id), 0)

def test_follow_up_phrases_are_current_turn_only(self) -> None:
    first = self.run_workflow("订单 ORD-1001 帮我催物流。", session_id="SESSION-TURN")
    second = self.run_workflow("订单现在到哪了？", session_id="SESSION-TURN")
    self.assertTrue(first.follow_up_requested)
    self.assertFalse(second.follow_up_requested)
```

节点顺序断言更新为：`order_query -> session_binding_check -> logistics_query`，以及 `abnormal_check -> follow_up_check -> query_rewrite`。

- [ ] **步骤 2：运行定向测试并确认新行为失败**

运行：`/opt/anaconda3/envs/rag_910/bin/python -m pytest tests/test_copilot_workflow.py -q`

预期：FAIL，缺少新节点/状态字段，且旧逻辑会为普通“没收到”建单。

- [ ] **步骤 3：实现两个规则节点和状态字段**

`CopilotState` 新增：

```python
active_session_ticket: Ticket | None = None
follow_up_requested: bool = False
ticket_association: Literal["created", "reused", "session_linked", "none"] = "none"
```

`follow_up_check_node` 仅匹配本轮消息中的固定短语：

```python
FOLLOW_UP_PHRASES = (
    "催一下", "催物流", "催快递", "继续催", "继续跟进", "帮我跟进",
    "帮我催", "加急", "尽快处理", "联系快递", "联系物流",
)

state.follow_up_requested = any(
    phrase in state.payload.user_message for phrase in FOLLOW_UP_PHRASES
)
```

`session_binding_check_node` 对无绑定、同订单活动工单、同订单非活动历史分别记录成功 Step；跨订单记录失败 Step 后抛出包含 `code/bound_order_id/requested_order_id` 的 HTTP 409。

- [ ] **步骤 4：重写工单决策并限制历史回退**

`ticket_create_node` 按固定优先级赋值：

```python
if state.intent != "logistics_delay":
    return record_none(state)
if state.active_session_ticket is not None:
    return link_session_ticket(state)
if state.order.status != "shipped" or not state.is_abnormal or not state.follow_up_requested:
    return record_none(state)
ticket = find_global_active_ticket(...) or create_ticket(...)
state.ticket_association = "reused" if reused else "created"
binding_service.bind_ticket(...)
```

`created/reused/session_linked` 都更新 `AgentRun.ticket_id`；只有 `reused` 新增 `copilot_followup_analyzed`，只有 `created` 允许飞书通知。`order_extract_node` 查询历史 Run 时增加 `AgentRun.status == "success"`，并按 `user_id` 或匿名 `NULL` 作用域过滤。

- [ ] **步骤 5：运行工作流测试确认通过**

运行：`/opt/anaconda3/envs/rag_910/bin/python -m pytest tests/test_copilot_workflow.py tests/test_feishu_service.py -q`

预期：全部 PASS；Step 顺序包含两个新节点，普通追问关联而不重复发通知。

- [ ] **步骤 6：提交任务 2**

```bash
git add agents services/session_ticket_binding_service.py tests/test_copilot_workflow.py
git commit -m "feat: enforce session-aware ticket workflow"
```

### 任务 3：API 契约、冲突副作用与边界场景

**文件：**
- 修改：`schemas/copilot.py`
- 修改：`services/copilot_service.py`
- 修改：`tests/test_copilot_analyze_api.py`

- [ ] **步骤 1：编写 API 失败测试**

新增对四态响应及 409 的真实 API 测试：

```python
def test_same_session_cross_order_returns_409_without_mutating_binding(self) -> None:
    first = self.analyze("SESSION-CONFLICT", "USER-001", "订单 ORD-1001 没收到，帮我催一下。")
    conflict = self.analyze("SESSION-CONFLICT", "USER-001", "查一下订单 ORD-1002。")
    self.assertEqual(conflict.status_code, 409)
    self.assertEqual(conflict.json()["detail"], {
        "code": "session_order_mismatch",
        "bound_order_id": "ORD-1001",
        "requested_order_id": "ORD-1002",
    })
    self.assertEqual(self.binding("SESSION-CONFLICT", "USER-001").ticket_id, first.json()["ticket_id"])
    self.assertEqual(self.latest_run().status, "failed")

def test_different_users_can_reuse_same_session_id_for_different_orders(self) -> None:
    self.assertEqual(self.analyze("SESSION-SHARED", "USER-001", self.followup_1001).status_code, 200)
    self.assertEqual(self.analyze("SESSION-SHARED", "USER-002", "查订单 ORD-1002").status_code, 200)

def test_anonymous_scope_is_stable(self) -> None:
    first = self.analyze("SESSION-ANON", None, self.followup_1001).json()
    second = self.analyze("SESSION-ANON", None, "现在进展怎么样？").json()
    self.assertEqual(second["ticket_association"], "session_linked")
    self.assertEqual(second["ticket_id"], first["ticket_id"])
```

另外断言 409 Run 只有 `intent_recognition/order_extract/order_query/session_binding_check`，Redis `append_turn` 未调用，物流、RAG、建单和飞书 Step 不存在。

- [ ] **步骤 2：运行 API 测试并确认响应字段和 409 断言失败**

运行：`/opt/anaconda3/envs/rag_910/bin/python -m pytest tests/test_copilot_analyze_api.py -q`

预期：FAIL，响应模型缺少 `ticket_association`，旧异常物流断言与新规则不一致。

- [ ] **步骤 3：实现成功响应和失败路径**

响应模型新增：

```python
ticket_association: Literal["created", "reused", "session_linked", "none"]
```

`analyze_after_sales_issue` 从状态返回该字段；保留兼容布尔值，仅当关联结果分别为 `created/reused` 时为真。HTTPException 路径不追加 Redis 会话内容，先确保当前事务可提交失败 Step 和 Run 状态，再原样抛出 409。

- [ ] **步骤 4：补齐关闭、重开、并发幂等场景**

使用现有工单 action API 验证：已解决工单再次明确催办创建新工单并刷新绑定；已解决工单重新打开后普通追问返回 `session_linked`。对相同会话连续重复提交断言数据库只有一个绑定；唯一约束竞争由服务层重读逻辑覆盖。

- [ ] **步骤 5：运行后端 M10.8 定向测试**

运行：`/opt/anaconda3/envs/rag_910/bin/python -m pytest tests/test_session_ticket_binding_service.py tests/test_copilot_workflow.py tests/test_copilot_analyze_api.py tests/test_business_api.py -q`

预期：全部 PASS，旧 `ticket_created/ticket_reused` 调用方仍兼容。

- [ ] **步骤 6：提交任务 3**

```bash
git add schemas/copilot.py services/copilot_service.py tests/test_copilot_analyze_api.py tests/test_copilot_workflow.py
git commit -m "feat: expose session ticket association contract"
```

### 任务 4：前端关联状态与 409 恢复交互

**文件：**
- 修改：`frontend/src/services/api.ts`
- 修改：`frontend/src/CopilotAnalysisContext.tsx`
- 修改：`frontend/src/App.tsx`
- 修改：`frontend/src/App.test.tsx`
- 修改：`frontend/src/styles.css`（仅在现有 Alert 布局需要少量操作区样式时修改）

- [ ] **步骤 1：编写前端失败测试**

用 axios mock 覆盖：

```typescript
it.each([
  ["created", "已创建待处理工单"],
  ["reused", "已复用已有待处理工单"],
  ["session_linked", "已关联会话工单"],
  ["none", "未关联工单"],
])("renders %s ticket association", async (association, expected) => { ... });

it("keeps draft and messages unchanged after session order conflict", async () => {
  mockedAxios.post.mockRejectedValue({ response: { status: 409, data: { detail: {
    code: "session_order_mismatch",
    bound_order_id: "ORD-1001",
    requested_order_id: "ORD-1002",
  } } } });
  await user.type(screen.getByLabelText("用户问题"), "查订单 ORD-1002");
  await user.click(screen.getByRole("button", { name: "开始分析" }));
  expect(await screen.findByText(/当前会话已绑定订单 ORD-1001/)).toBeInTheDocument();
  expect(screen.getByLabelText("用户问题")).toHaveValue("查订单 ORD-1002");
  expect(screen.queryByLabelText("当前咨询记录")).not.toBeInTheDocument();
});

it("starts a new session while preserving the conflict draft", async () => {
  const originalSession = screen.getByText(/当前会话：/).textContent;
  await user.click(screen.getByRole("button", { name: "新建咨询" }));
  expect(screen.getByLabelText("用户问题")).toHaveValue("查订单 ORD-1002");
  expect(screen.getByText(/当前会话：/).textContent).not.toBe(originalSession);
});
```

- [ ] **步骤 2：运行前端测试并确认新断言失败**

运行：`cd frontend && npm run test:run -- src/App.test.tsx`

预期：FAIL，API 类型没有 `ticket_association`，409 仍显示通用错误且新建咨询清空草稿。

- [ ] **步骤 3：实现结构化冲突状态与草稿保留**

定义：

```typescript
export type TicketAssociation = "created" | "reused" | "session_linked" | "none";
export type SessionOrderMismatch = {
  code: "session_order_mismatch";
  bound_order_id: string;
  requested_order_id: string;
};
```

Context 增加 `sessionOrderMismatch`。409 时保存 detail、不修改 `messages/result/draft`；普通错误仍走现有错误文案。`startNewConversation` 先判断是否存在冲突：始终重置 session/messages/result/error，只有非冲突时清空 draft。

- [ ] **步骤 4：实现四态文案和冲突操作**

使用映射直接展示：

```typescript
const ticketAssociationLabels = {
  created: "已创建待处理工单",
  reused: "已复用已有待处理工单",
  session_linked: "已关联会话工单",
  none: "未关联工单",
};
```

409 Alert 描述同时展示绑定订单、本轮订单，并提供调用现有 `startNewConversation` 的“新建咨询”按钮；不创建第二套会话重置逻辑。

- [ ] **步骤 5：运行前端测试确认通过**

运行：`cd frontend && npm run test:run -- src/App.test.tsx`

预期：全部 PASS；四态文案和冲突恢复均可被 Testing Library 操作验证。

- [ ] **步骤 6：提交任务 4**

```bash
git add frontend/src/services/api.ts frontend/src/CopilotAnalysisContext.tsx frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/styles.css
git commit -m "feat: handle session order conflicts in workspace"
```

### 任务 5：全量验证、手工 API 验收与状态更新

**文件：**
- 修改：`docs/STATUS.md`

- [ ] **步骤 1：运行后端全量测试**

运行：`/opt/anaconda3/envs/rag_910/bin/python -m pytest -q`

预期：全部 PASS，无失败或错误。

- [ ] **步骤 2：运行前端全量测试和生产构建**

运行：`cd frontend && npm run test:run`

预期：全部 PASS。

运行：`cd frontend && npm run build`

预期：退出码 0；允许保留既有 Vite 大 chunk 警告，不新增 TypeScript 错误。

- [ ] **步骤 3：验证 Compose 配置**

运行：`docker compose config --quiet`

预期：退出码 0，无配置错误。

- [ ] **步骤 4：执行手工 API 验收**

启动：`uvicorn api.main:app --host 127.0.0.1 --port 8000`

依次请求：

```bash
curl -s -X POST http://127.0.0.1:8000/api/copilot/analyze -H 'Content-Type: application/json' -d '{"session_id":"M10-8-MANUAL","user_id":"USER-001","user_message":"订单 ORD-1001 没收到，帮我催一下物流。"}'
curl -s -X POST http://127.0.0.1:8000/api/copilot/analyze -H 'Content-Type: application/json' -d '{"session_id":"M10-8-MANUAL","user_id":"USER-001","user_message":"现在进展怎么样？"}'
curl -s -o /tmp/m10-8-conflict.json -w '%{http_code}' -X POST http://127.0.0.1:8000/api/copilot/analyze -H 'Content-Type: application/json' -d '{"session_id":"M10-8-MANUAL","user_id":"USER-001","user_message":"查订单 ORD-1002"}'
```

预期：第一次为 `created` 或在已有本地活动单时为 `reused`，第二次为 `session_linked` 且 `ticket_id` 相同，第三次状态码为 `409` 且 detail 含两个订单号。

- [ ] **步骤 5：更新状态文档**

在 `docs/STATUS.md` 将 M10.8 标为完成，记录：持久会话绑定、明确催办信号、四态响应、409 前端恢复、最终测试计数；下一里程碑保持为 M10.6。

- [ ] **步骤 6：重跑文档变更后的最终验证并提交**

运行：

```bash
/opt/anaconda3/envs/rag_910/bin/python -m pytest -q
cd frontend && npm run test:run
cd frontend && npm run build
docker compose config --quiet
```

预期：四条命令全部退出码 0。

提交：

```bash
git add docs/STATUS.md
git commit -m "docs: mark M10.8 session binding complete"
```

