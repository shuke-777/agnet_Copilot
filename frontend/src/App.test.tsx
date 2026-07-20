import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

vi.mock("axios");

const mockedAxios = vi.mocked(axios, { deep: true });

describe("App", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    mockedAxios.get.mockReset();
    mockedAxios.post.mockReset();
  });

  it("renders the Copilot workspace by default and navigates to tickets", async () => {
    const user = (await import("@testing-library/user-event")).default.setup();

    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Copilot 工作台" })).toBeInTheDocument();
    expect(screen.getByText("本地演示环境")).toBeInTheDocument();
    expect(screen.queryByText("M8 前端工作台")).not.toBeInTheDocument();
    expect(screen.queryByText("M8.6 业务关联")).not.toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "工单中心" }));

    expect(await screen.findByRole("heading", { name: "工单中心" })).toBeInTheDocument();
    expect(screen.getByText("实时协同")).toBeInTheDocument();
    expect(screen.queryByText("M8.6 业务关联")).not.toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "操作日志" }));

    expect(await screen.findByRole("heading", { name: "操作日志" })).toBeInTheDocument();
    expect(screen.getByText("全局操作流水")).toBeInTheDocument();
  });

  it("filters operation logs by business correlation fields", async () => {
    const user = userEvent.setup();
    mockedAxios.get.mockResolvedValue({ data: [] });

    render(<MemoryRouter initialEntries={["/operation-logs"]}><App /></MemoryRouter>);

    expect(await screen.findByRole("heading", { name: "操作日志" })).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "筛选操作人" }), "客服A");
    await user.type(screen.getByRole("textbox", { name: "筛选工单 ID" }), "TCK-1001");
    await user.click(screen.getByRole("button", { name: /筛\s*选/ }));

    await waitFor(() => {
      expect(mockedAxios.get).toHaveBeenLastCalledWith("/api/operation-logs", {
        params: { operator: "客服A", ticket_id: "TCK-1001" },
      });
    });
  });

  it("submits an after-sales question and renders the Copilot analysis result", async () => {
    const user = userEvent.setup();
    mockedAxios.post.mockResolvedValue({
      data: {
        run_id: "RUN-1001",
        status: "running",
        events_url: "/api/runs/RUN-1001/events",
      },
    });
    mockedAxios.get.mockImplementation((url) => {
      if (url === "/api/runs/RUN-1001") {
        return Promise.resolve({
          data: {
            run_id: "RUN-1001",
            session_id: "WEB-1001",
            user_id: "客服A",
            user_message: "订单 ORD-1001 一直没收到，帮我催一下物流。",
            order_id: "ORD-1001",
            ticket_id: "TCK-1001",
            intent: "logistics_delay",
            status: "success",
            total_duration_ms: 38,
            result_payload: JSON.stringify({
              run_id: "RUN-1001",
              intent: "logistics_delay",
              order_id: "ORD-1001",
              is_abnormal: true,
              reply_draft: "物流超过 72 小时未更新，已为您创建催物流工单。",
              ticket_created: true,
              ticket_reused: false,
              ticket_association: "created",
              ticket_id: "TCK-1001",
              approval_required: false,
              approval_status: "not_required",
              approval_reason: "物流催办不涉及资金、库存或权益变更",
              feishu_status: "disabled",
              policy_sources: [
                {
                  source_id: "logistics_delay_72h_sop",
                  title: "物流超过 72 小时未更新处理 SOP",
                  content: "核实物流卡点后创建催物流工单。",
                  score: 0.92,
                },
              ],
            }),
            created_at: "2026-07-14T10:00:00",
            finished_at: "2026-07-14T10:00:01",
          },
        });
      }
      if (url === "/api/runs/RUN-1001/steps") {
        return Promise.resolve({
          data: [
            {
              step_id: "STP-1001",
              run_id: "RUN-1001",
              step_name: "intent_recognition",
              step_type: "agent",
              status: "success",
              start_time: "2026-07-14T10:00:00",
              end_time: "2026-07-14T10:00:00",
              duration_ms: 3,
              input_summary: "订单未收到",
              output_summary: "识别物流异常意图",
              error_message: null,
              llm_provider: "disabled",
              llm_model: null,
              input_tokens: null,
              output_tokens: null,
              fallback_reason: "LLM provider is disabled",
              cache_hit: false,
            },
          ],
        });
      }
      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    render(
      <MemoryRouter initialEntries={["/workspace"]}>
        <App />
      </MemoryRouter>,
    );

    await user.type(
      screen.getByRole("textbox", { name: "用户问题" }),
      "订单 ORD-1001 一直没收到，帮我催一下物流。",
    );
    await user.click(screen.getByRole("button", { name: /开始分析/ }));

    expect(mockedAxios.post).toHaveBeenCalledWith(
      "/api/copilot/analyze/start",
      expect.objectContaining({
        user_message: "订单 ORD-1001 一直没收到，帮我催一下物流。",
      }),
    );
    expect(await screen.findByText("实时链路")).toBeInTheDocument();
    expect(await screen.findByText("物流超过 72 小时未更新，已为您创建催物流工单。"))
      .toBeInTheDocument();
    expect(screen.getByText("TCK-1001")).toBeInTheDocument();
    expect(screen.getByText("RUN-1001")).toBeInTheDocument();
    expect(screen.getByText("物流超过 72 小时未更新处理 SOP")).toBeInTheDocument();
  });

  it("shows the retry time when Copilot analysis is rate limited", async () => {
    const user = userEvent.setup();
    mockedAxios.post.mockRejectedValue({
      response: {
        status: 429,
        data: {
          detail: {
            code: "copilot_rate_limited",
            retry_after_seconds: 17,
          },
        },
      },
    });

    render(<MemoryRouter initialEntries={["/workspace"]}><App /></MemoryRouter>);
    await user.type(screen.getByRole("textbox", { name: "用户问题" }), "订单 ORD-1001 怎么还没收到？");
    await user.click(screen.getByRole("button", { name: /开始分析/ }));

    expect(await screen.findByText("请求过于频繁，请在 17 秒后重试。")).toBeInTheDocument();
  });

  it("keeps one session across turns and lets the agent start a new consultation", async () => {
    const user = userEvent.setup();
    mockedAxios.post.mockResolvedValue({
      data: {
        run_id: "RUN-CONTEXT-001",
        status: "running",
        events_url: "/api/runs/RUN-CONTEXT-001/events",
      },
    });
    mockedAxios.get.mockImplementation((url) => {
      if (url === "/api/runs/RUN-CONTEXT-001") {
        return Promise.resolve({
          data: {
            run_id: "RUN-CONTEXT-001",
            session_id: "WEB-1001",
            user_id: "客服A",
            user_message: "订单 ORD-1001 还没收到。",
            order_id: "ORD-1001",
            ticket_id: null,
            intent: "logistics_delay",
            status: "success",
            total_duration_ms: 12,
            result_payload: JSON.stringify({
              run_id: "RUN-CONTEXT-001",
              intent: "logistics_delay",
              order_id: "ORD-1001",
              is_abnormal: true,
              reply_draft: "已记录本次咨询。",
              ticket_created: false,
              ticket_reused: false,
              ticket_association: "none",
              ticket_id: null,
              approval_required: false,
              approval_status: "not_required",
              approval_reason: "物流催办不涉及资金、库存或权益变更",
              feishu_status: "skipped",
              policy_sources: [],
            }),
            created_at: "2026-07-14T10:00:00",
            finished_at: "2026-07-14T10:00:01",
          },
        });
      }
      if (url === "/api/runs/RUN-CONTEXT-001/steps") {
        return Promise.resolve({
          data: [
            {
              step_id: "STP-1",
              run_id: "RUN-CONTEXT-001",
              step_name: "intent_recognition",
              step_type: "agent",
              status: "success",
              start_time: "2026-07-14T10:00:00",
              end_time: "2026-07-14T10:00:00",
              duration_ms: 2,
              input_summary: null,
              output_summary: null,
              error_message: null,
              llm_provider: null,
              llm_model: null,
              input_tokens: null,
              output_tokens: null,
              fallback_reason: null,
              cache_hit: false,
            },
          ],
        });
      }
      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    render(<MemoryRouter initialEntries={["/workspace"]}><App /></MemoryRouter>);
    const input = screen.getByRole("textbox", { name: "用户问题" });
    await user.type(input, "订单 ORD-1001 还没收到。");
    await user.click(screen.getByRole("button", { name: /开始分析/ }));
    await screen.findByText("已记录本次咨询。");

    await user.type(input, "请继续跟进。");
    await user.click(screen.getByRole("button", { name: /开始分析/ }));

    const firstPayload = mockedAxios.post.mock.calls[0][1] as { session_id: string };
    const secondPayload = mockedAxios.post.mock.calls[1][1] as { session_id: string; history: Array<{ content: string }> };
    expect(secondPayload.session_id).toBe(firstPayload.session_id);
    expect(secondPayload.history[0].content).toBe("订单 ORD-1001 还没收到。");

    await user.click(screen.getByRole("button", { name: "新建咨询" }));
    expect(screen.getByRole("textbox", { name: "用户问题" })).toHaveValue("");
    expect(screen.queryByText("已记录本次咨询。")).not.toBeInTheDocument();
  });

  it.each([
    ["created", "已创建待处理工单", "TCK-ASSOCIATION"],
    ["reused", "已复用已有待处理工单", "TCK-ASSOCIATION"],
    ["session_linked", "已关联会话工单", "TCK-ASSOCIATION"],
    ["none", "未关联工单", null],
  ] as const)("renders the %s ticket association", async (ticketAssociation, expectedLabel, ticketId) => {
    const user = userEvent.setup();
    mockedAxios.post.mockResolvedValue({
      data: {
        run_id: `RUN-${ticketAssociation}`,
        status: "running",
        events_url: `/api/runs/RUN-${ticketAssociation}/events`,
      },
    });
    mockedAxios.get.mockImplementation((url) => {
      if (url === `/api/runs/RUN-${ticketAssociation}`) {
        return Promise.resolve({
          data: {
            run_id: `RUN-${ticketAssociation}`,
            session_id: "WEB-1001",
            user_id: "客服A",
            user_message: "订单 ORD-1001 的物流情况",
            order_id: "ORD-1001",
            ticket_id: ticketId,
            intent: "logistics_delay",
            status: "success",
            total_duration_ms: 12,
            result_payload: JSON.stringify({
              run_id: `RUN-${ticketAssociation}`,
              intent: "logistics_delay",
              order_id: "ORD-1001",
              is_abnormal: true,
              reply_draft: "已生成处理建议。",
              ticket_created: ticketAssociation === "created",
              ticket_reused: ticketAssociation === "reused",
              ticket_association: ticketAssociation,
              ticket_id: ticketId,
              approval_required: false,
              approval_status: "not_required",
              approval_reason: "物流催办不涉及资金、库存或权益变更",
              feishu_status: "skipped",
              policy_sources: [],
            }),
            created_at: "2026-07-14T10:00:00",
            finished_at: "2026-07-14T10:00:01",
          },
        });
      }
      if (url === `/api/runs/RUN-${ticketAssociation}/steps`) {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    render(<MemoryRouter initialEntries={["/workspace"]}><App /></MemoryRouter>);
    await user.type(screen.getByRole("textbox", { name: "用户问题" }), "订单 ORD-1001 的物流情况");
    await user.click(screen.getByRole("button", { name: /开始分析/ }));

    expect((await screen.findAllByText(expectedLabel)).length).toBeGreaterThan(0);
  });

  it("preserves the draft and starts a clean session after an order conflict", async () => {
    const user = userEvent.setup();
    mockedAxios.post.mockRejectedValue({
      response: {
        status: 409,
        data: {
          detail: {
            code: "session_order_mismatch",
            bound_order_id: "ORD-1001",
            requested_order_id: "ORD-1002",
          },
        },
      },
    });

    render(<MemoryRouter initialEntries={["/workspace"]}><App /></MemoryRouter>);
    const input = screen.getByRole("textbox", { name: "用户问题" });
    const originalSession = screen.getByText(/当前会话：/).textContent;
    await user.type(input, "查订单 ORD-1002");
    await user.click(screen.getByRole("button", { name: /开始分析/ }));

    expect(await screen.findByText(/当前会话已绑定订单 ORD-1001，本轮识别订单 ORD-1002/))
      .toBeInTheDocument();
    expect(input).toHaveValue("查订单 ORD-1002");
    expect(screen.queryByLabelText("当前咨询记录")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "冲突后新建咨询" }));

    expect(input).toHaveValue("查订单 ORD-1002");
    expect(screen.getByText(/当前会话：/).textContent).not.toBe(originalSession);
    expect(screen.queryByText(/当前会话已绑定订单/)).not.toBeInTheDocument();
  });

  it("loads tickets, opens the detail page, and lets an agent claim a ticket", async () => {
    const user = userEvent.setup();
    mockedAxios.get.mockImplementation((url) => {
      if (url === "/api/tickets") {
        return Promise.resolve({
          data: [
            {
              ticket_id: "TCK-1001",
              ticket_type: "logistics_delay",
              priority: "high",
              status: "todo",
              user_id: "USER-001",
              order_id: "ORD-1001",
              summary: "订单一直未收到，需要催物流。",
              suggested_action: "联系承运商核实卡点。",
              assigned_to: null,
              created_by: "agent",
              approval_required: false,
              approval_status: "not_required",
              approval_reason: null,
              approval_decided_by: null,
              approval_decided_at: null,
              created_at: "2026-07-13T10:00:00",
              updated_at: "2026-07-13T10:00:00",
              events: [],
            },
          ],
        });
      }
      if (url === "/api/tickets/TCK-1001") {
        return Promise.resolve({
          data: {
            ticket_id: "TCK-1001",
            ticket_type: "logistics_delay",
            priority: "high",
            status: "todo",
            user_id: "USER-001",
            order_id: "ORD-1001",
            summary: "订单一直未收到，需要催物流。",
            suggested_action: "联系承运商核实卡点。",
            assigned_to: null,
            created_by: "agent",
            approval_required: false,
            approval_status: "not_required",
            approval_reason: null,
            approval_decided_by: null,
            approval_decided_at: null,
            created_at: "2026-07-13T10:00:00",
            updated_at: "2026-07-13T10:00:00",
            events: [
              {
                event_id: "EVT-1001",
                ticket_id: "TCK-1001",
                event_type: "ticket_created",
                operator: "agent",
                content: "Agent 创建工单。",
                from_status: null,
                to_status: "todo",
                created_at: "2026-07-13T10:00:00",
              },
            ],
          },
        });
      }
      if (url === "/api/orders/ORD-1001") {
        return Promise.resolve({ data: { order_id: "ORD-1001", product_name: "无线蓝牙耳机", status: "shipped", amount: 199 } });
      }
      if (url === "/api/logistics/ORD-1001") {
        return Promise.resolve({ data: { carrier: "顺丰速运", tracking_no: "SF1001001001", status: "stalled", last_event: "物流超过 72 小时未更新", is_abnormal: true } });
      }
      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });
    mockedAxios.post.mockResolvedValue({
      data: {
        ticket_id: "TCK-1001",
        ticket_type: "logistics_delay",
        priority: "high",
        status: "processing",
        user_id: "USER-001",
        order_id: "ORD-1001",
        summary: "订单一直未收到，需要催物流。",
        suggested_action: "联系承运商核实卡点。",
        assigned_to: "客服A",
        created_by: "agent",
        approval_required: false,
        approval_status: "not_required",
        approval_reason: null,
        approval_decided_by: null,
        approval_decided_at: null,
        created_at: "2026-07-13T10:00:00",
        updated_at: "2026-07-13T10:01:00",
        events: [],
      },
    });

    render(
      <MemoryRouter initialEntries={["/tickets"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("TCK-1001")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: "TCK-1001" }));

    expect(await screen.findByRole("heading", { name: "工单 TCK-1001" })).toBeInTheDocument();
    expect(screen.getByText("无线蓝牙耳机")).toBeInTheDocument();
    expect(screen.getByText("Agent 创建工单。")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "接单处理" }));
    expect(mockedAxios.post).toHaveBeenCalledWith("/api/tickets/TCK-1001/actions", {
      action: "claim",
      operator: "客服A",
    });
    expect(await screen.findByText("状态已更新：processing")).toBeInTheDocument();
  });

  it("renders a continuous proportional waterfall and switches details from its legend", async () => {
    const user = userEvent.setup();
    mockedAxios.get.mockImplementation((url) => {
      if (url === "/api/runs") {
        return Promise.resolve({
          data: [{
            run_id: "RUN-1001",
            session_id: "WEB-1001",
            user_id: "客服A",
            user_message: "订单 ORD-1001 一直没收到。",
            intent: "logistics_delay",
            status: "success",
            total_duration_ms: 38,
            created_at: "2026-07-14T10:00:00",
            finished_at: "2026-07-14T10:00:01",
          }],
        });
      }
      if (url === "/api/runs/RUN-1001") {
        return Promise.resolve({
          data: {
            run_id: "RUN-1001",
            session_id: "WEB-1001",
            user_id: "客服A",
            user_message: "订单 ORD-1001 一直没收到。",
            intent: "logistics_delay",
            status: "success",
            total_duration_ms: 38,
            created_at: "2026-07-14T10:00:00",
            finished_at: "2026-07-14T10:00:01",
          },
        });
      }
      if (url === "/api/runs/RUN-1001/steps") {
        return Promise.resolve({
          data: [
            {
              step_id: "STP-1001",
              run_id: "RUN-1001",
              step_name: "intent_recognition",
              step_type: "agent",
              status: "success",
              start_time: "2026-07-14T10:00:00",
              end_time: "2026-07-14T10:00:00",
              duration_ms: 3,
              input_summary: "订单未收到",
              output_summary: "识别物流异常意图",
              error_message: null,
              llm_provider: "openai_compatible",
              llm_model: "test-model",
              input_tokens: 24,
              output_tokens: 8,
              fallback_reason: null,
            },
            {
              step_id: "STP-1002",
              run_id: "RUN-1001",
              step_name: "order_query",
              step_type: "tool",
              status: "success",
              start_time: "2026-07-14T10:00:00.003",
              end_time: "2026-07-14T10:00:00.008",
              duration_ms: 5,
              input_summary: "查询订单 ORD-1001",
              output_summary: "订单已发货",
              error_message: null,
            },
            {
              step_id: "STP-1003",
              run_id: "RUN-1001",
              step_name: "policy_retrieval",
              step_type: "rag",
              status: "failed",
              start_time: "2026-07-14T10:00:01",
              end_time: "2026-07-14T10:00:01",
              duration_ms: 30,
              input_summary: "物流异常催单",
              output_summary: null,
              error_message: "知识库暂不可用",
            },
            {
              step_id: "STP-1004",
              run_id: "RUN-1001",
              step_name: "feishu_notify",
              step_type: "webhook",
              status: "skipped",
              start_time: "2026-07-14T10:00:02",
              end_time: "2026-07-14T10:00:02",
              duration_ms: 0,
              input_summary: "TCK-1001",
              output_summary: "Webhook 未配置",
              error_message: null,
            },
          ],
        });
      }
      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    render(
      <MemoryRouter initialEntries={["/runs"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("RUN-1001")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: "RUN-1001" }));

    expect(await screen.findByRole("heading", { name: "Agent Run RUN-1001" })).toBeInTheDocument();
    expect(screen.getByText("总耗时 38 ms")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "轨道节点 intent_recognition" })).toHaveStyle({ flexBasis: "7.894737%" });
    expect(screen.getByRole("button", { name: "轨道节点 order_query" })).toHaveStyle({ flexBasis: "13.157895%" });
    expect(screen.getByRole("button", { name: "轨道节点 policy_retrieval" })).toHaveStyle({ flexBasis: "78.947368%" });
    expect(screen.queryByRole("button", { name: "轨道节点 feishu_notify" })).not.toBeInTheDocument();
    const skippedLegendItem = screen.getByRole("button", { name: "图例节点 feishu_notify" });
    expect(skippedLegendItem).toBeInTheDocument();
    expect(skippedLegendItem.querySelector(".trace-legend-swatch")).toHaveClass("trace-segment-skipped");
    expect(screen.getByRole("button", { name: "轨道节点 intent_recognition" })).toHaveClass("trace-segment-agent");
    expect(screen.getByRole("button", { name: "轨道节点 order_query" })).toHaveClass("trace-segment-tool");
    expect(screen.getByRole("button", { name: "轨道节点 policy_retrieval" })).toHaveClass("trace-segment-failed");
    expect(await screen.findByText("输出：识别物流异常意图")).toBeInTheDocument();
    expect(screen.getByText("模型：openai_compatible / test-model；输入 Token：24；输出 Token：8")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "轨道节点 policy_retrieval" }));
    expect(await screen.findByText("错误：知识库暂不可用")).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "图例节点 feishu_notify" }));
    expect(await screen.findByText("输出：Webhook 未配置")).toBeInTheDocument();
    expect(screen.getByText("skipped")).toBeInTheDocument();
  });

  it("shows an empty waterfall state when a run has no recorded steps", async () => {
    mockedAxios.get.mockImplementation((url) => {
      if (url === "/api/runs/RUN-EMPTY") {
        return Promise.resolve({
          data: {
            run_id: "RUN-EMPTY",
            session_id: "WEB-EMPTY",
            user_id: "客服A",
            user_message: "测试空链路",
            intent: null,
            status: "success",
            total_duration_ms: 0,
            created_at: "2026-07-14T10:00:00",
            finished_at: "2026-07-14T10:00:00",
          },
        });
      }
      if (url === "/api/runs/RUN-EMPTY/steps") {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    render(
      <MemoryRouter initialEntries={["/runs/RUN-EMPTY"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("该 Run 暂无可展示的 Step 记录。")).toBeInTheDocument();
  });

  it("loads live dashboard metrics, distributions, and agent performance", async () => {
    mockedAxios.get.mockImplementation((url) => {
      if (url === "/api/dashboard/overview") {
        return Promise.resolve({
          data: {
            ticket_total: 12,
            pending_ticket_count: 5,
            high_priority_pending_ticket_count: 2,
            agent_run_total: 20,
            average_run_duration_ms: 486.5,
            agent_run_success_rate: 0.95,
            feishu_notification_attempt_count: 8,
            feishu_notification_success_rate: 0.875,
          },
        });
      }
      if (url === "/api/dashboard/ticket-stats") {
        return Promise.resolve({
          data: {
            status_counts: [{ key: "todo", count: 3 }, { key: "resolved", count: 7 }],
            priority_counts: [{ key: "high", count: 2 }, { key: "normal", count: 8 }],
          },
        });
      }
      if (url === "/api/dashboard/agent-performance") {
        return Promise.resolve({
          data: {
            agent_run_total: 20,
            average_run_duration_ms: 486.5,
            agent_run_success_rate: 0.95,
            step_performance: [{
              step_name: "policy_retrieval",
              count: 20,
              success_count: 19,
              failed_count: 1,
              success_rate: 0.95,
              average_duration_ms: 125.4,
            }],
          },
        });
      }
      if (url === "/api/dashboard/risk-ranking") {
        return Promise.resolve({
          data: {
            source: "redis",
            carrier_risks: [{ key: "顺丰速运", score: 3, count: 3 }],
            high_priority_tickets: [{ key: "TCK-RISK-001", score: 1, count: 1 }],
            frequent_issue_risks: [{ key: "logistics_delay", score: 6, count: 6 }],
          },
        });
      }
      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByLabelText("指标 工单总量: 12")).toBeInTheDocument();
    expect(screen.getByLabelText("指标 待处理工单: 5")).toBeInTheDocument();
    expect(screen.getByLabelText("指标 Agent 成功率: 95.0%")).toBeInTheDocument();
    expect(screen.getByLabelText("指标 飞书通知成功率: 87.5%")).toBeInTheDocument();
    expect(screen.getByText("工单状态分布")).toBeInTheDocument();
    expect(screen.getByText("运营风险榜")).toBeInTheDocument();
    expect(screen.getByText("顺丰速运")).toBeInTheDocument();
    expect(screen.getByText("TCK-RISK-001")).toBeInTheDocument();
    expect(screen.getByText("logistics_delay")).toBeInTheDocument();
    expect(screen.getAllByText("policy_retrieval")).toHaveLength(1);
    expect(mockedAxios.get).toHaveBeenCalledWith("/api/dashboard/overview");
    expect(mockedAxios.get).toHaveBeenCalledWith("/api/dashboard/ticket-stats");
    expect(mockedAxios.get).toHaveBeenCalledWith("/api/dashboard/agent-performance");
    expect(mockedAxios.get).toHaveBeenCalledWith("/api/dashboard/risk-ranking");
  });

  it("keeps dashboard metrics visible when a secondary dashboard request fails", async () => {
    mockedAxios.get.mockImplementation((url) => {
      if (url === "/api/dashboard/overview") {
        return Promise.resolve({
          data: {
            ticket_total: 1,
            pending_ticket_count: 1,
            high_priority_pending_ticket_count: 1,
            agent_run_total: 1,
            average_run_duration_ms: null,
            agent_run_success_rate: 1,
            feishu_notification_attempt_count: 0,
            feishu_notification_success_rate: null,
          },
        });
      }
      if (url === "/api/dashboard/ticket-stats") {
        return Promise.reject(new Error("network error"));
      }
      if (url === "/api/dashboard/agent-performance") {
        return Promise.resolve({
          data: {
            agent_run_total: 1,
            average_run_duration_ms: null,
            agent_run_success_rate: 1,
            step_performance: [],
          },
        });
      }
      if (url === "/api/dashboard/risk-ranking") {
        return Promise.reject(new Error("network error"));
      }
      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByLabelText("指标 工单总量: 1")).toBeInTheDocument();
    expect(await screen.findByText("部分运营数据暂时无法加载，请稍后刷新重试。"))
      .toBeInTheDocument();
  });
});
