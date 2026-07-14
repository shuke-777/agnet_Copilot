import axios from "axios";

export type PolicySource = {
  source_id: string;
  title: string;
  content: string;
  score: number;
};

export type CopilotAnalyzeResponse = {
  run_id: string;
  intent: string;
  order_id: string;
  is_abnormal: boolean;
  reply_draft: string;
  ticket_created: boolean;
  ticket_id: string | null;
  feishu_status: string;
  policy_sources: PolicySource[];
};

export type TicketEvent = {
  event_id: string;
  ticket_id: string;
  event_type: string;
  operator: string;
  content: string;
  from_status: string | null;
  to_status: string | null;
  created_at: string;
};

export type Ticket = {
  ticket_id: string;
  ticket_type: string;
  priority: string;
  status: string;
  user_id: string;
  order_id: string;
  source_run_id: string | null;
  source_run_created_at: string | null;
  summary: string;
  suggested_action: string;
  assigned_to: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  events: TicketEvent[];
};

export type Order = {
  order_id: string;
  product_name: string;
  status: string;
  amount: number;
};

export type Logistics = {
  carrier: string;
  tracking_no: string;
  status: string;
  last_event: string;
  is_abnormal: boolean;
};

export type AgentRun = {
  run_id: string;
  session_id: string;
  user_id: string | null;
  user_message: string;
  order_id: string | null;
  ticket_id: string | null;
  intent: string | null;
  status: string;
  total_duration_ms: number | null;
  created_at: string;
  finished_at: string | null;
};

export type AgentStep = {
  step_id: string;
  run_id: string;
  step_name: string;
  step_type: string;
  status: string;
  start_time: string;
  end_time: string | null;
  duration_ms: number | null;
  input_summary: string | null;
  output_summary: string | null;
  error_message: string | null;
  llm_provider?: string | null;
  llm_model?: string | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  fallback_reason?: string | null;
};

export type MetricCount = { key: string; count: number };

export type DashboardOverview = {
  ticket_total: number;
  pending_ticket_count: number;
  high_priority_pending_ticket_count: number;
  agent_run_total: number;
  average_run_duration_ms: number | null;
  agent_run_success_rate: number | null;
  feishu_notification_attempt_count: number;
  feishu_notification_success_rate: number | null;
};

export type TicketStats = { status_counts: MetricCount[]; priority_counts: MetricCount[] };

export type StepPerformance = {
  step_name: string;
  count: number;
  success_count: number;
  failed_count: number;
  success_rate: number | null;
  average_duration_ms: number | null;
};

export type AgentPerformance = {
  agent_run_total: number;
  average_run_duration_ms: number | null;
  agent_run_success_rate: number | null;
  step_performance: StepPerformance[];
};

type AnalyzeCopilotInput = {
  session_id: string;
  user_id: string;
  user_message: string;
  history?: Array<{ role: "user" | "assistant"; content: string }>;
};

export async function analyzeCopilot(input: AnalyzeCopilotInput): Promise<CopilotAnalyzeResponse> {
  const response = await axios.post<CopilotAnalyzeResponse>("/api/copilot/analyze", input);
  return response.data;
}

export async function listTickets(query?: string): Promise<Ticket[]> {
  const response = await axios.get<Ticket[]>("/api/tickets", { params: query ? { q: query } : undefined });
  return response.data;
}

export async function getTicket(ticketId: string): Promise<Ticket> {
  const response = await axios.get<Ticket>(`/api/tickets/${ticketId}`);
  return response.data;
}

export async function getOrder(orderId: string): Promise<Order> {
  const response = await axios.get<Order>(`/api/orders/${orderId}`);
  return response.data;
}

export async function getLogistics(orderId: string): Promise<Logistics> {
  const response = await axios.get<Logistics>(`/api/logistics/${orderId}`);
  return response.data;
}

export async function applyTicketAction(
  ticketId: string,
  action: "claim" | "resolve" | "reopen",
  operator: string,
): Promise<Ticket> {
  const response = await axios.post<Ticket>(`/api/tickets/${ticketId}/actions`, { action, operator });
  return response.data;
}

export async function listAgentRuns(query?: string): Promise<AgentRun[]> {
  const response = await axios.get<AgentRun[]>("/api/runs", { params: query ? { q: query } : undefined });
  return response.data;
}

export async function getAgentRun(runId: string): Promise<AgentRun> {
  const response = await axios.get<AgentRun>(`/api/runs/${runId}`);
  return response.data;
}

export async function listAgentSteps(runId: string): Promise<AgentStep[]> {
  const response = await axios.get<AgentStep[]>(`/api/runs/${runId}/steps`);
  return response.data;
}

export async function getDashboardOverview(): Promise<DashboardOverview> {
  const response = await axios.get<DashboardOverview>("/api/dashboard/overview");
  return response.data;
}

export async function getDashboardTicketStats(): Promise<TicketStats> {
  const response = await axios.get<TicketStats>("/api/dashboard/ticket-stats");
  return response.data;
}

export async function getAgentPerformance(): Promise<AgentPerformance> {
  const response = await axios.get<AgentPerformance>("/api/dashboard/agent-performance");
  return response.data;
}
