import {
  BarChartOutlined,
  CheckCircleOutlined,
  FileSearchOutlined,
  InboxOutlined,
  ArrowLeftOutlined,
  PlusOutlined,
  SendOutlined,
  RobotOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Avatar,
  Badge,
  Button,
  Descriptions,
  Divider,
  Form,
  Input,
  Layout,
  Menu,
  Space,
  Spin,
  Tag,
  Table,
  Timeline,
  Typography,
} from "antd";
import type { MenuProps } from "antd";
import { useEffect, useState } from "react";
import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Link, NavLink, Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";

import {
  analyzeCopilot,
  applyTicketAction,
  getAgentPerformance,
  getAgentRun,
  getDashboardOverview,
  getDashboardTicketStats,
  getLogistics,
  getOrder,
  getTicket,
  listAgentRuns,
  listAgentSteps,
  listTickets,
} from "./services/api";
import { CopilotAnalysisProvider, useCopilotAnalysis } from "./CopilotAnalysisContext";
import type {
  AgentPerformance,
  AgentRun,
  AgentStep,
  CopilotAnalyzeResponse,
  DashboardOverview,
  Logistics,
  Order,
  Ticket,
  TicketStats,
} from "./services/api";

const { Header, Content, Sider } = Layout;
const { Title, Text } = Typography;

type NavigationItem = Required<MenuProps>["items"][number];

const navigationItems: NavigationItem[] = [
  { key: "/workspace", icon: <InboxOutlined />, label: <NavLink to="/workspace">Copilot 工作台</NavLink> },
  { key: "/tickets", icon: <FileSearchOutlined />, label: <NavLink to="/tickets">工单中心</NavLink> },
  { key: "/runs", icon: <RobotOutlined />, label: <NavLink to="/runs">Agent 追踪</NavLink> },
  { key: "/dashboard", icon: <BarChartOutlined />, label: <NavLink to="/dashboard">运营看板</NavLink> },
];

function PageHeader({ title, description, extra }: { title: string; description: string; extra?: React.ReactNode }) {
  return (
    <div className="page-heading">
      <div>
        <Title level={2}>{title}</Title>
        <Text type="secondary">{description}</Text>
      </div>
      {extra || <Tag color="blue">M8.6 业务关联</Tag>}
    </div>
  );
}

function formatPercentage(value: number | null | undefined): string {
  return value === null || value === undefined ? "-" : `${(value * 100).toFixed(1)}%`;
}

function WorkspacePage() {
  const { analyze, draft, errorMessage, isAnalyzing, messages, result, sessionId, setDraft, startNewConversation } = useCopilotAnalysis();

  return (
    <section>
      <PageHeader
        title="Copilot 工作台"
        description="处理售后咨询、生成处理建议并保留人工确认节点。"
        extra={<Button aria-label="新建咨询" icon={<PlusOutlined />} onClick={startNewConversation} disabled={isAnalyzing}>新建咨询</Button>}
      />
      <div className="workspace-grid">
        <article className="work-panel work-panel-primary">
          <Text className="panel-eyebrow">待处理咨询</Text>
          <Title level={4}>提交一条售后咨询</Title>
          <Form layout="vertical" onFinish={analyze} requiredMark={false}>
            <Form.Item
              label="用户问题"
            >
              <Input.TextArea
                aria-label="用户问题"
                autoSize={{ minRows: 4, maxRows: 7 }}
                placeholder="例如：订单 ORD-1001 一直没收到，帮我催一下物流。"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
              />
            </Form.Item>
            <Button htmlType="submit" icon={<SendOutlined />} loading={isAnalyzing} disabled={!draft.trim()} type="primary">
              开始分析
            </Button>
          </Form>
        </article>
        <article className="work-panel">
          <Text className="panel-eyebrow">人工 Checkpoint</Text>
          <div className="metric-row">
            <strong>{result?.ticket_id ? "1" : "0"}</strong>
            <Text type="secondary">
              {result?.ticket_created ? "已创建待处理工单" : result?.ticket_reused ? "已关联已有待处理工单" : "等待人工确认"}
            </Text>
          </div>
          <Text type="secondary">当前会话：{sessionId}。系统只给出建议与创建结果，状态推进仍由人工确认。</Text>
        </article>
      </div>

      {messages.length > 0 && (
        <article className="conversation-history" aria-label="当前咨询记录">
          {messages.filter((message) => message.role === "user").map((message, index) => (
            <div className="conversation-user-message" key={`${message.content}-${index}`}>咨询 {index + 1}：{message.content}</div>
          ))}
        </article>
      )}

      {isAnalyzing && (
        <div className="analysis-loading" role="status">
          <Spin />
          <Text>Copilot 正在查询订单、物流和售后规则...</Text>
        </div>
      )}

      {errorMessage && <Alert className="analysis-alert" message={errorMessage} showIcon type="error" />}

      {result && (
        <div className="analysis-result">
          <div className="result-heading">
            <div>
              <Text className="panel-eyebrow">Copilot 分析结果</Text>
              <Title level={4}>处理建议已生成</Title>
            </div>
            <Tag color={result.is_abnormal ? "volcano" : "green"}>
              {result.is_abnormal ? "物流异常" : "物流正常"}
            </Tag>
          </div>

          <Descriptions bordered column={{ xs: 1, sm: 2, lg: 4 }} size="small">
            <Descriptions.Item label="识别意图">{result.intent}</Descriptions.Item>
            <Descriptions.Item label="订单号">{result.order_id || "未识别"}</Descriptions.Item>
            <Descriptions.Item label="工单结果">
              {result.ticket_id ? <Link to={`/tickets/${result.ticket_id}`}>{result.ticket_reused ? `${result.ticket_id}（已复用）` : result.ticket_id}</Link> : "未创建工单"}
            </Descriptions.Item>
            <Descriptions.Item label="飞书通知">{result.feishu_status}</Descriptions.Item>
          </Descriptions>

          <Divider />
          <div className="result-section">
            <Text className="panel-eyebrow">客服回复草稿</Text>
            <div className="reply-draft">{result.reply_draft}</div>
          </div>

          <Divider />
          <div className="result-section">
            <Text className="panel-eyebrow">RAG 规则依据</Text>
            {result.policy_sources.length > 0 ? (
              <div className="policy-list">
                {result.policy_sources.map((policy) => (
                  <article className="policy-item" key={policy.source_id}>
                    <div className="policy-title-row">
                      <strong>{policy.title}</strong>
                      <Tag>{Math.round(policy.score * 100)}% 匹配</Tag>
                    </div>
                    <Text type="secondary">{policy.content}</Text>
                  </article>
                ))}
              </div>
            ) : (
              <Text type="secondary">本次未召回可展示的售后规则。</Text>
            )}
          </div>

          <Divider />
          <div className="trace-row">
            <Space size="small">
              <CheckCircleOutlined />
              <Text type="secondary">Agent Run</Text>
              <Link to={`/runs/${result.run_id}`}><Text code>{result.run_id}</Text></Link>
            </Space>
            {result.ticket_created && <Tag color="blue">已创建催物流工单</Tag>}
            {result.ticket_reused && <Tag color="cyan">已关联已有工单</Tag>}
          </div>
        </div>
      )}
    </section>
  );
}

const tagColorByStatus: Record<string, string> = {
  todo: "gold",
  processing: "blue",
  resolved: "green",
  high: "volcano",
  normal: "blue",
  low: "default",
};

function StatusTag({ value }: { value: string }) {
  return <Tag color={tagColorByStatus[value]}>{value}</Tag>;
}

function formatDuration(duration: number | null | undefined) {
  return duration === null || duration === undefined ? "-" : `${duration} ms`;
}

function sortAgentSteps(steps: AgentStep[]) {
  return [...steps].sort((left, right) => left.start_time.localeCompare(right.start_time));
}

function traceSegmentClass(step: AgentStep) {
  if (step.status === "failed") return "trace-segment-failed";
  if (step.status === "skipped") return "trace-segment-skipped";
  return `trace-segment-${step.step_type}`;
}

function TraceWaterfall({
  steps,
  selectedStepId,
  onSelect,
}: {
  steps: AgentStep[];
  selectedStepId: string | null;
  onSelect: (stepId: string) => void;
}) {
  if (steps.length === 0) {
    return <Text type="secondary">该 Run 暂无可展示的 Step 记录。</Text>;
  }

  const totalDuration = steps.reduce((total, step) => total + Math.max(step.duration_ms ?? 0, 0), 0);
  const visibleSteps = totalDuration > 0
    ? steps.filter((step) => (step.duration_ms ?? 0) > 0)
    : [];

  return (
    <div className="trace-waterfall">
      <div className="trace-waterfall-summary">
        <strong>执行时间占比</strong>
        <span>总耗时 {formatDuration(totalDuration)}</span>
      </div>
      <div className="trace-waterfall-track" role="group" aria-label="Agent Step 执行瀑布图">
        {visibleSteps.map((step) => {
          const duration = step.duration_ms ?? 0;
          const isSelected = step.step_id === selectedStepId;
          return (
            <button
              aria-pressed={isSelected}
              aria-label={`轨道节点 ${step.step_name}`}
              className={`trace-segment ${traceSegmentClass(step)}${isSelected ? " trace-segment-selected" : ""}`}
              key={step.step_id}
              onClick={() => onSelect(step.step_id)}
              style={{ flexBasis: `${((duration / totalDuration) * 100).toFixed(6)}%` }}
              title={`${step.step_name}: ${formatDuration(duration)}`}
              type="button"
            />
          );
        })}
      </div>
      <div className="trace-waterfall-legend" aria-label="Agent Step 图例">
        {steps.map((step) => {
          const isSelected = step.step_id === selectedStepId;
          return (
            <button
              aria-pressed={isSelected}
              aria-label={`图例节点 ${step.step_name}`}
              className={`trace-legend-item${isSelected ? " trace-legend-item-selected" : ""}`}
              key={step.step_id}
              onClick={() => onSelect(step.step_id)}
              type="button"
            >
              <span className={`trace-legend-swatch ${traceSegmentClass(step)}`} />
              <span>{step.step_name}</span>
              {step.cache_hit && <Tag color="cyan">缓存命中</Tag>}
              <span className="trace-legend-duration">{formatDuration(step.duration_ms)}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function TicketsPage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const { refreshToken } = useCopilotAnalysis();

  useEffect(() => {
    let isCurrent = true;
    setIsLoading(true);
    listTickets(query)
      .then((data) => {
        if (isCurrent) setTickets(data);
      })
      .catch(() => {
        if (isCurrent) setErrorMessage("工单列表暂时无法加载，请确认后端服务已启动。");
      })
      .finally(() => {
        if (isCurrent) setIsLoading(false);
      });
    return () => {
      isCurrent = false;
    };
  }, [query, refreshToken]);

  const columns = [
    {
      title: "工单 ID",
      dataIndex: "ticket_id",
      render: (ticketId: string) => <Link to={`/tickets/${ticketId}`}>{ticketId}</Link>,
    },
    { title: "订单号", dataIndex: "order_id" },
    {
      title: "来源 Run",
      dataIndex: "source_run_id",
      render: (runId: string | null) => runId ? <Link to={`/runs/${runId}`}>{runId}</Link> : "人工创建",
    },
    {
      title: "Agent 调用时间",
      dataIndex: "source_run_created_at",
      render: (value: string | null) => value ? new Date(value).toLocaleString("zh-CN") : "-",
    },
    { title: "类型", dataIndex: "ticket_type" },
    { title: "优先级", dataIndex: "priority", render: (value: string) => <StatusTag value={value} /> },
    { title: "状态", dataIndex: "status", render: (value: string) => <StatusTag value={value} /> },
    { title: "处理人", dataIndex: "assigned_to", render: (value: string | null) => value || "未分配" },
    { title: "摘要", dataIndex: "summary", ellipsis: true },
  ];

  return (
    <section>
      <PageHeader title="工单中心" description="集中查看催物流工单和人工处理状态。" />
      {errorMessage && <Alert className="analysis-alert" message={errorMessage} showIcon type="error" />}
      <article className="data-panel">
        <Input.Search
          allowClear
          className="table-search"
          placeholder="搜索工单 ID、Run ID 或订单号"
          value={query}
          onChange={(event) => { if (!event.target.value) setQuery(""); }}
          onSearch={(value) => setQuery(value.trim())}
        />
        <Table<Ticket>
          columns={columns}
          dataSource={tickets}
          loading={isLoading}
          pagination={{ pageSize: 8, hideOnSinglePage: true }}
          rowKey="ticket_id"
          locale={{ emptyText: "暂无工单，请先在 Copilot 工作台提交一条异常物流咨询。" }}
        />
      </article>
    </section>
  );
}

function TicketDetailPage() {
  const { ticketId = "" } = useParams();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [order, setOrder] = useState<Order | null>(null);
  const [logistics, setLogistics] = useState<Logistics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    let isCurrent = true;
    getTicket(ticketId)
      .then(async (ticketData) => {
        const [orderData, logisticsData] = await Promise.all([getOrder(ticketData.order_id), getLogistics(ticketData.order_id)]);
        if (!isCurrent) return;
        setTicket(ticketData);
        setOrder(orderData);
        setLogistics(logisticsData);
      })
      .catch(() => {
        if (isCurrent) setErrorMessage("工单详情暂时无法加载，请确认工单 ID 和后端服务。");
      })
      .finally(() => {
        if (isCurrent) setIsLoading(false);
      });
    return () => {
      isCurrent = false;
    };
  }, [ticketId]);

  const handleAction = async (action: "claim" | "resolve" | "reopen") => {
    if (!ticket) return;
    setIsUpdating(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const updatedTicket = await applyTicketAction(ticket.ticket_id, action, "客服A");
      setTicket(updatedTicket);
      setSuccessMessage(`状态已更新：${updatedTicket.status}`);
    } catch {
      setErrorMessage("状态更新未完成，请刷新后确认工单当前状态再重试。");
    } finally {
      setIsUpdating(false);
    }
  };

  if (isLoading) {
    return <div className="analysis-loading" role="status"><Spin /><Text>正在加载工单详情...</Text></div>;
  }

  if (!ticket) {
    return <Alert message={errorMessage || "未找到工单。"} showIcon type="error" />;
  }

  const action = ticket.status === "todo" ? ["claim", "接单处理"] as const
    : ticket.status === "processing" ? ["resolve", "标记已解决"] as const
      : ticket.status === "resolved" ? ["reopen", "重新打开"] as const
        : null;

  return (
    <section>
      <div className="detail-heading">
        <div>
          <Link className="back-link" to="/tickets"><ArrowLeftOutlined /> 返回工单中心</Link>
          <Title level={2}>工单 {ticket.ticket_id}</Title>
          <Text type="secondary">由 {ticket.created_by} 创建于 {new Date(ticket.created_at).toLocaleString("zh-CN")}</Text>
        </div>
        <Space>
          <StatusTag value={ticket.priority} />
          <StatusTag value={ticket.status} />
          {action && <Button loading={isUpdating} onClick={() => handleAction(action[0])} type="primary">{action[1]}</Button>}
        </Space>
      </div>
      {errorMessage && <Alert className="analysis-alert" message={errorMessage} showIcon type="error" />}
      {successMessage && <Alert className="analysis-alert" message={successMessage} showIcon type="success" />}
      <div className="ticket-detail-grid">
        <article className="data-panel">
          <Text className="panel-eyebrow">工单信息</Text>
          <Descriptions column={2} size="small">
            <Descriptions.Item label="订单号">{ticket.order_id}</Descriptions.Item>
            <Descriptions.Item label="来源 Run">{ticket.source_run_id ? <Link to={`/runs/${ticket.source_run_id}`}>{ticket.source_run_id}</Link> : "人工创建，无关联 Run"}</Descriptions.Item>
            <Descriptions.Item label="处理人">{ticket.assigned_to || "未分配"}</Descriptions.Item>
            <Descriptions.Item label="问题摘要" span={2}>{ticket.summary}</Descriptions.Item>
            <Descriptions.Item label="建议动作" span={2}>{ticket.suggested_action}</Descriptions.Item>
          </Descriptions>
        </article>
        <article className="data-panel">
          <Text className="panel-eyebrow">订单与物流</Text>
          <Descriptions column={1} size="small">
            <Descriptions.Item label="商品">{order?.product_name || "-"}</Descriptions.Item>
            <Descriptions.Item label="订单金额">{order ? `¥${order.amount}` : "-"}</Descriptions.Item>
            <Descriptions.Item label="承运商">{logistics?.carrier || "-"}</Descriptions.Item>
            <Descriptions.Item label="运单号">{logistics?.tracking_no || "-"}</Descriptions.Item>
            <Descriptions.Item label="最新物流">{logistics?.last_event || "-"}</Descriptions.Item>
          </Descriptions>
        </article>
      </div>
      <article className="data-panel timeline-panel">
        <Text className="panel-eyebrow">关联 Agent Run</Text>
        {(ticket.related_runs ?? []).length > 0 ? (
          <Space wrap size={[8, 8]}>
            {ticket.related_runs.map((run) => (
              <Link key={run.run_id} to={`/runs/${run.run_id}`}>
                <Tag color={run.run_id === ticket.source_run_id ? "blue" : "cyan"}>
                  {run.run_id === ticket.source_run_id ? "来源 " : "追加 "}{run.run_id}
                </Tag>
              </Link>
            ))}
          </Space>
        ) : (
          <Text type="secondary">暂无关联 Agent Run。</Text>
        )}
      </article>
      <article className="data-panel timeline-panel">
        <Text className="panel-eyebrow">工单事件</Text>
        <Timeline
          items={ticket.events.map((event) => ({
            children: <><strong>{event.content}</strong><br /><Text type="secondary">{event.operator} · {new Date(event.created_at).toLocaleString("zh-CN")}</Text></>,
            color: event.to_status === "resolved" ? "green" : "blue",
          }))}
        />
      </article>
    </section>
  );
}

function RunsPage() {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const { refreshToken } = useCopilotAnalysis();

  useEffect(() => {
    let isCurrent = true;
    setIsLoading(true);
    listAgentRuns(query)
      .then((data) => {
        if (isCurrent) setRuns(data);
      })
      .catch(() => {
        if (isCurrent) setErrorMessage("Agent Run 列表暂时无法加载，请确认后端服务已启动。");
      })
      .finally(() => {
        if (isCurrent) setIsLoading(false);
      });
    return () => {
      isCurrent = false;
    };
  }, [query, refreshToken]);

  const columns = [
    { title: "工单 ID", dataIndex: "ticket_id", render: (ticketId: string | null) => ticketId ? <Link to={`/tickets/${ticketId}`}>{ticketId}</Link> : "未创建工单" },
    { title: "Run ID", dataIndex: "run_id", render: (runId: string) => <Link to={`/runs/${runId}`}>{runId}</Link> },
    { title: "订单号", dataIndex: "order_id", render: (value: string | null) => value || "未识别" },
    { title: "用户问题", dataIndex: "user_message", ellipsis: true },
    { title: "意图", dataIndex: "intent", render: (value: string | null) => value || "未识别" },
    { title: "状态", dataIndex: "status", render: (value: string) => <StatusTag value={value} /> },
    { title: "总耗时", dataIndex: "total_duration_ms", render: (value: number | null) => formatDuration(value) },
    { title: "创建时间", dataIndex: "created_at", render: (value: string) => new Date(value).toLocaleString("zh-CN") },
  ];

  return (
    <section>
      <PageHeader title="Agent 追踪" description="查看每次 Copilot 执行的步骤、状态和耗时。" />
      {errorMessage && <Alert className="analysis-alert" message={errorMessage} showIcon type="error" />}
      <article className="data-panel">
        <Input.Search
          allowClear
          className="table-search"
          placeholder="搜索工单 ID、Run ID 或订单号"
          value={query}
          onChange={(event) => { if (!event.target.value) setQuery(""); }}
          onSearch={(value) => setQuery(value.trim())}
        />
        <Table<AgentRun>
          columns={columns}
          dataSource={runs}
          loading={isLoading}
          pagination={{ pageSize: 8, hideOnSinglePage: true }}
          rowKey="run_id"
          locale={{ emptyText: "暂无 Agent Run，请先在 Copilot 工作台执行一次分析。" }}
        />
      </article>
    </section>
  );
}

function RunDetailPage() {
  const { runId = "" } = useParams();
  const [run, setRun] = useState<AgentRun | null>(null);
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let isCurrent = true;
    Promise.all([getAgentRun(runId), listAgentSteps(runId)])
      .then(([runData, stepData]) => {
        if (!isCurrent) return;
        setRun(runData);
        const sortedSteps = sortAgentSteps(stepData);
        setSteps(sortedSteps);
        setSelectedStepId(sortedSteps[0]?.step_id ?? null);
      })
      .catch(() => {
        if (isCurrent) setErrorMessage("Agent Run 详情暂时无法加载，请确认 Run ID 和后端服务。");
      })
      .finally(() => {
        if (isCurrent) setIsLoading(false);
      });
    return () => {
      isCurrent = false;
    };
  }, [runId]);

  if (isLoading) {
    return <div className="analysis-loading" role="status"><Spin /><Text>正在加载 Agent 执行链路...</Text></div>;
  }
  if (!run) {
    return <Alert message={errorMessage || "未找到 Agent Run。"} showIcon type="error" />;
  }

  const selectedStep = steps.find((step) => step.step_id === selectedStepId) ?? null;

  return (
    <section>
      <div className="detail-heading">
        <div>
          <Link className="back-link" to="/runs"><ArrowLeftOutlined /> 返回 Agent 追踪</Link>
          <Title level={2}>Agent Run {run.run_id}</Title>
          <Text type="secondary">创建于 {new Date(run.created_at).toLocaleString("zh-CN")}</Text>
        </div>
        <StatusTag value={run.status} />
      </div>
      <div className="ticket-detail-grid">
        <article className="data-panel">
          <Text className="panel-eyebrow">执行概览</Text>
          <Descriptions column={2} size="small">
            <Descriptions.Item label="意图">{run.intent || "未识别"}</Descriptions.Item>
            <Descriptions.Item label="总耗时">{formatDuration(run.total_duration_ms)}</Descriptions.Item>
            <Descriptions.Item label="会话 ID">{run.session_id}</Descriptions.Item>
            <Descriptions.Item label="用户">{run.user_id || "-"}</Descriptions.Item>
            <Descriptions.Item label="用户问题" span={2}>{run.user_message}</Descriptions.Item>
          </Descriptions>
        </article>
        <article className="data-panel">
          <Text className="panel-eyebrow">执行结果</Text>
          <Descriptions column={1} size="small">
            <Descriptions.Item label="状态"><StatusTag value={run.status} /></Descriptions.Item>
            <Descriptions.Item label="完成时间">{run.finished_at ? new Date(run.finished_at).toLocaleString("zh-CN") : "执行中"}</Descriptions.Item>
            <Descriptions.Item label="Step 数量">{steps.length}</Descriptions.Item>
          </Descriptions>
        </article>
      </div>
      <article className="data-panel timeline-panel">
        <Text className="panel-eyebrow">Step 执行瀑布图</Text>
        <TraceWaterfall steps={steps} selectedStepId={selectedStepId} onSelect={setSelectedStepId} />
        {selectedStep && (
          <div className="trace-step-detail">
            <div className="trace-step-detail-heading">
              <Space wrap size="small">
                <strong>{selectedStep.step_name}</strong>
                <Tag>{selectedStep.step_type}</Tag>
                <StatusTag value={selectedStep.status} />
                {selectedStep.cache_hit && <Tag color="cyan">RAG 缓存命中</Tag>}
                <Text type="secondary">{formatDuration(selectedStep.duration_ms)}</Text>
              </Space>
              <Text type="secondary">
                {new Date(selectedStep.start_time).toLocaleTimeString("zh-CN")} - {selectedStep.end_time ? new Date(selectedStep.end_time).toLocaleTimeString("zh-CN") : "执行中"}
              </Text>
            </div>
            {selectedStep.input_summary && <Text className="step-summary" type="secondary">输入：{selectedStep.input_summary}</Text>}
            {selectedStep.output_summary && <Text className="step-summary">输出：{selectedStep.output_summary}</Text>}
            {selectedStep.error_message && <Text className="step-summary" type="danger">错误：{selectedStep.error_message}</Text>}
            {selectedStep.llm_provider && <Text className="step-summary" type="secondary">模型：{selectedStep.llm_provider}{selectedStep.llm_model ? ` / ${selectedStep.llm_model}` : ""}；输入 Token：{selectedStep.input_tokens ?? "-"}；输出 Token：{selectedStep.output_tokens ?? "-"}</Text>}
            {selectedStep.fallback_reason && <Text className="step-summary" type="warning">降级：{selectedStep.fallback_reason}</Text>}
          </div>
        )}
      </article>
    </section>
  );
}

function DashboardPage() {
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [ticketStats, setTicketStats] = useState<TicketStats | null>(null);
  const [agentPerformance, setAgentPerformance] = useState<AgentPerformance | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [hasPartialError, setHasPartialError] = useState(false);

  useEffect(() => {
    let isCurrent = true;
    Promise.allSettled([getDashboardOverview(), getDashboardTicketStats(), getAgentPerformance()])
      .then(([overviewResult, ticketStatsResult, agentPerformanceResult]) => {
        if (!isCurrent) return;
        if (overviewResult.status === "fulfilled") setOverview(overviewResult.value);
        if (ticketStatsResult.status === "fulfilled") setTicketStats(ticketStatsResult.value);
        if (agentPerformanceResult.status === "fulfilled") setAgentPerformance(agentPerformanceResult.value);
        setHasPartialError([overviewResult, ticketStatsResult, agentPerformanceResult].some((result) => result.status === "rejected"));
      })
      .finally(() => {
        if (isCurrent) setIsLoading(false);
      });
    return () => { isCurrent = false; };
  }, []);

  const metricCards = [
    ["工单总量", overview?.ticket_total ?? "-", "累计进入售后流程的工单"],
    ["待处理工单", overview?.pending_ticket_count ?? "-", `其中高优先级 ${overview?.high_priority_pending_ticket_count ?? "-"}`],
    ["Agent 成功率", formatPercentage(overview?.agent_run_success_rate), `共 ${overview?.agent_run_total ?? "-"} 次运行`],
    ["飞书通知成功率", formatPercentage(overview?.feishu_notification_success_rate), `已尝试 ${overview?.feishu_notification_attempt_count ?? "-"} 次`],
  ] as const;
  const statusColors = ["#5b7cfa", "#48bdb9", "#f0a23a", "#9365c7", "#8b96a8"];
  const priorityColors = ["#cf3f4f", "#f0a23a", "#5b7cfa", "#8b96a8"];
  const stepColumns = [
    { title: "Step", dataIndex: "step_name" },
    { title: "执行次数", dataIndex: "count", width: 100 },
    { title: "成功", dataIndex: "success_count", width: 80 },
    { title: "失败", dataIndex: "failed_count", width: 80 },
    { title: "成功率", dataIndex: "success_rate", width: 100, render: (value: number | null) => formatPercentage(value) },
    { title: "平均耗时", dataIndex: "average_duration_ms", width: 115, render: (value: number | null) => formatDuration(value) },
  ];

  return (
    <section>
      <PageHeader title="运营看板" description="关注工单处理、Agent 成功率与通知结果。" />
      {hasPartialError && <Alert className="analysis-alert" message="部分运营数据暂时无法加载，请稍后刷新重试。" showIcon type="warning" />}
      {isLoading ? <div className="analysis-loading" role="status"><Spin /><Text>正在加载运营数据...</Text></div> : <>
        <div className="dashboard-placeholder">
          {metricCards.map(([label, value, hint]) => <article aria-label={`指标 ${label}: ${value}`} className="metric-card" key={label}>
            <Text type="secondary">{label}</Text><strong>{value}</strong><Text type="secondary">{hint}</Text>
          </article>)}
        </div>
        <div className="dashboard-chart-grid">
          <article className="data-panel dashboard-chart-panel">
            <Text className="panel-eyebrow">工单状态分布</Text>
            {ticketStats?.status_counts.length ? <ResponsiveContainer height={240} width="100%"><BarChart data={ticketStats.status_counts} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}><XAxis dataKey="key" tickLine={false} axisLine={false} /><YAxis allowDecimals={false} tickLine={false} axisLine={false} /><Tooltip cursor={{ fill: "#f1f5f9" }} /><Bar dataKey="count" name="工单数" radius={[4, 4, 0, 0]}>{ticketStats.status_counts.map((item, index) => <Cell fill={statusColors[index % statusColors.length]} key={item.key} />)}</Bar></BarChart></ResponsiveContainer> : <DashboardEmpty text="暂无工单状态数据。" />}
          </article>
          <article className="data-panel dashboard-chart-panel">
            <Text className="panel-eyebrow">工单优先级分布</Text>
            {ticketStats?.priority_counts.length ? <div className="dashboard-pie-layout"><ResponsiveContainer height={220} width="55%"><PieChart><Tooltip /><Pie data={ticketStats.priority_counts} dataKey="count" nameKey="key" innerRadius={52} outerRadius={82} paddingAngle={2}>{ticketStats.priority_counts.map((item, index) => <Cell fill={priorityColors[index % priorityColors.length]} key={item.key} />)}</Pie></PieChart></ResponsiveContainer><div className="dashboard-legend">{ticketStats.priority_counts.map((item, index) => <div key={item.key}><i style={{ background: priorityColors[index % priorityColors.length] }} />{item.key}<strong>{item.count}</strong></div>)}</div></div> : <DashboardEmpty text="暂无工单优先级数据。" />}
          </article>
        </div>
        <article className="data-panel dashboard-performance-panel">
          <div className="dashboard-performance-heading"><div><Text className="panel-eyebrow">Agent Step 性能</Text><Text type="secondary">平均 Run 耗时：{formatDuration(agentPerformance?.average_run_duration_ms)}</Text></div><Tag color={agentPerformance?.agent_run_success_rate === 1 ? "green" : "blue"}>运行成功率 {formatPercentage(agentPerformance?.agent_run_success_rate)}</Tag></div>
          <Table columns={stepColumns} dataSource={agentPerformance?.step_performance ?? []} pagination={false} rowKey="step_name" locale={{ emptyText: "暂无 Agent Step 性能数据。" }} size="middle" />
        </article>
      </>}
    </section>
  );
}

function DashboardEmpty({ text }: { text: string }) {
  return <div className="dashboard-empty"><Text type="secondary">{text}</Text></div>;
}

function AppShell() {
  const location = useLocation();
  const { errorMessage, isAnalyzing, result } = useCopilotAnalysis();

  return (
    <Layout className="app-shell">
      <Sider breakpoint="lg" collapsedWidth="0" className="app-sider" width={236}>
        <div className="brand-mark">
          <span className="brand-icon"><RobotOutlined /></span>
          <span>AfterSales Copilot</span>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={navigationItems}
        />
        <div className="sider-footer">
          <Badge status="processing" text="服务运行中" />
          <Text type="secondary">M8 前端工作台</Text>
        </div>
      </Sider>
      <Layout>
        <Header className="app-header">
          <Text className="header-context">售后运营中心</Text>
          <Space size="middle">
            {location.pathname !== "/workspace" && isAnalyzing && <Link to="/workspace"><Badge status="processing" text="Copilot 分析中" /></Link>}
            {location.pathname !== "/workspace" && !isAnalyzing && result && <Link to={`/runs/${result.run_id}`}><Badge status="success" text="最近分析已完成" /></Link>}
            {location.pathname !== "/workspace" && errorMessage && <Link to="/workspace"><Badge status="error" text="最近分析失败" /></Link>}
            <Button type="text">帮助</Button>
            <Avatar size="small">A</Avatar>
            <Text>客服A</Text>
          </Space>
        </Header>
        <Content className="app-content">
          <Routes>
            <Route path="/" element={<Navigate to="/workspace" replace />} />
            <Route path="/workspace" element={<WorkspacePage />} />
            <Route path="/tickets" element={<TicketsPage />} />
            <Route path="/tickets/:ticketId" element={<TicketDetailPage />} />
            <Route path="/runs" element={<RunsPage />} />
            <Route path="/runs/:runId" element={<RunDetailPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="*" element={<Navigate to="/workspace" replace />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}

export default function App() {
  return <CopilotAnalysisProvider><AppShell /></CopilotAnalysisProvider>;
}
