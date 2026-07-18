import { getAgentRun, getAgentRunResult, listAgentSteps } from "./services/api";
import type { AgentRun, AgentStep, CopilotAnalyzeResponse } from "./services/api";

export function sortAgentSteps(steps: AgentStep[]) {
  return [...steps].sort((left, right) => left.start_time.localeCompare(right.start_time));
}

function parseEventData<T>(event: MessageEvent<string>): T | null {
  try {
    return JSON.parse(event.data) as T;
  } catch {
    return null;
  }
}

function mergeSteps(current: AgentStep[], next: AgentStep[]): AgentStep[] {
  const merged = new Map<string, AgentStep>();
  for (const step of current) merged.set(step.step_id, step);
  for (const step of next) merged.set(step.step_id, step);
  return sortAgentSteps(Array.from(merged.values()));
}

type RunProgressHandlers = {
  onRunUpdate?: (run: AgentRun) => void;
  onStepsUpdate?: (steps: AgentStep[]) => void;
  onFinal?: (result: CopilotAnalyzeResponse, run: AgentRun) => void;
  onError?: (message: string) => void;
};

export function watchRunProgress(runId: string, handlers: RunProgressHandlers): () => void {
  let active = true;
  let source: EventSource | null = null;
  let fallbackStarted = false;
  let currentSteps: AgentStep[] = [];

  const cleanup = () => {
    active = false;
    if (source) {
      source.close();
      source = null;
    }
  };

  const publishSteps = (steps: AgentStep[]) => {
    currentSteps = mergeSteps(currentSteps, steps);
    handlers.onStepsUpdate?.(currentSteps);
  };

  const finishWithRun = async (run: AgentRun, result?: CopilotAnalyzeResponse | null) => {
    const finalResult = result ?? (run.result_payload ? JSON.parse(run.result_payload) as CopilotAnalyzeResponse : null) ?? await getAgentRunResult(runId).catch(() => null);
    if (finalResult) {
      handlers.onFinal?.(finalResult, run);
    } else {
      handlers.onError?.("分析结果暂时无法加载，请稍后刷新。");
    }
    cleanup();
  };

  const startPolling = async () => {
    if (fallbackStarted) return;
    fallbackStarted = true;
    try {
      while (active) {
        const [run, steps] = await Promise.all([getAgentRun(runId), listAgentSteps(runId)]);
        if (!active) return;
        handlers.onRunUpdate?.(run);
        publishSteps(steps);
        if (run.status === "success" || run.status === "failed") {
          if (run.status === "success") {
            await finishWithRun(run);
          } else {
            handlers.onError?.("Copilot 分析失败，请稍后重试。");
            cleanup();
          }
          return;
        }
        await new Promise((resolve) => {
          window.setTimeout(resolve, 500);
        });
      }
    } catch {
      if (active) {
        handlers.onError?.("实时链路暂时不可用，请刷新后重试。");
        cleanup();
      }
    }
  };

  if (typeof window !== "undefined" && "EventSource" in window) {
    source = new EventSource(`/api/runs/${runId}/events`);

    source.addEventListener("run_started", (event) => {
      const payload = parseEventData<{ run?: AgentRun }>(event as MessageEvent<string>);
      if (payload?.run) {
        handlers.onRunUpdate?.(payload.run);
      }
    });

    source.addEventListener("step_created", (event) => {
      const payload = parseEventData<{ step?: AgentStep }>(event as MessageEvent<string>);
      if (payload?.step) {
        publishSteps([payload.step]);
      }
    });

    source.addEventListener("run_finished", (event) => {
      const payload = parseEventData<{ run?: AgentRun; result?: CopilotAnalyzeResponse }>(event as MessageEvent<string>);
      if (payload?.run) {
        handlers.onRunUpdate?.(payload.run);
      }
      void finishWithRun(payload?.run ?? { run_id: runId } as AgentRun, payload?.result);
    });

    source.addEventListener("run_failed", (event) => {
      const payload = parseEventData<{ run?: AgentRun }>(event as MessageEvent<string>);
      if (payload?.run) {
        handlers.onRunUpdate?.(payload.run);
      }
      handlers.onError?.("Copilot 分析失败，请稍后重试。");
      cleanup();
    });

    source.onerror = () => {
      if (!active) return;
      source?.close();
      source = null;
      void startPolling();
    };

    return cleanup;
  }

  void startPolling();
  return cleanup;
}
