import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";

import { startCopilotAnalysis } from "./services/api";
import type { AgentStep, CopilotAnalyzeResponse, SessionOrderMismatch } from "./services/api";
import { watchRunProgress } from "./runProgress";

type ConversationMessage = {
  role: "user" | "assistant";
  content: string;
};

type CopilotAnalysisContextValue = {
  sessionId: string;
  messages: ConversationMessage[];
  draft: string;
  result: CopilotAnalyzeResponse | null;
  errorMessage: string | null;
  sessionOrderMismatch: SessionOrderMismatch | null;
  isAnalyzing: boolean;
  refreshToken: number;
  activeRunId: string | null;
  liveRunStatus: string | null;
  liveSteps: AgentStep[];
  setDraft: (draft: string) => void;
  analyze: () => Promise<void>;
  startNewConversation: () => void;
};

const CopilotAnalysisContext = createContext<CopilotAnalysisContextValue | null>(null);

let sessionSequence = 0;

function makeSessionId() {
  sessionSequence += 1;
  return `WEB-${Date.now()}-${sessionSequence}`;
}

function getSessionOrderMismatch(error: unknown): SessionOrderMismatch | null {
  const response = (error as {
    response?: { status?: number; data?: { detail?: Partial<SessionOrderMismatch> } };
  }).response;
  const detail = response?.data?.detail;
  if (
    response?.status === 409
    && detail?.code === "session_order_mismatch"
    && typeof detail.bound_order_id === "string"
    && typeof detail.requested_order_id === "string"
  ) {
    return detail as SessionOrderMismatch;
  }
  return null;
}

function getAnalysisErrorMessage(error: unknown) {
  const response = (error as {
    response?: { status?: number; data?: { detail?: { code?: string; retry_after_seconds?: number } } };
  }).response;
  const retryAfterSeconds = response?.data?.detail?.retry_after_seconds;
  if (response?.status === 429 && response.data?.detail?.code === "copilot_rate_limited" && retryAfterSeconds) {
    return `请求过于频繁，请在 ${retryAfterSeconds} 秒后重试。`;
  }
  return "分析请求未完成，请确认后端服务已启动后重试。";
}

export function CopilotAnalysisProvider({ children }: { children: React.ReactNode }) {
  const [sessionId, setSessionId] = useState(makeSessionId);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [result, setResult] = useState<CopilotAnalyzeResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [sessionOrderMismatch, setSessionOrderMismatch] = useState<SessionOrderMismatch | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [liveRunStatus, setLiveRunStatus] = useState<string | null>(null);
  const [liveSteps, setLiveSteps] = useState<AgentStep[]>([]);
  const progressCleanupRef = useRef<(() => void) | null>(null);

  const stopProgressTracking = useCallback(() => {
    progressCleanupRef.current?.();
    progressCleanupRef.current = null;
  }, []);

  const analyze = useCallback(async () => {
    const userMessage = draft.trim();
    if (!userMessage || isAnalyzing) return;

    setIsAnalyzing(true);
    setErrorMessage(null);
    setSessionOrderMismatch(null);
    setActiveRunId(null);
    setLiveRunStatus("running");
    setLiveSteps([]);
    stopProgressTracking();
    try {
      const startResponse = await startCopilotAnalysis({
        session_id: sessionId,
        user_id: "客服A",
        user_message: userMessage,
        history: messages.slice(-8),
      });

      setActiveRunId(startResponse.run_id);
      await new Promise<CopilotAnalyzeResponse>((resolve, reject) => {
        progressCleanupRef.current = watchRunProgress(startResponse.run_id, {
          onRunUpdate: (run) => {
            setActiveRunId(run.run_id);
            setLiveRunStatus(run.status);
          },
          onStepsUpdate: setLiveSteps,
          onFinal: (analysis) => {
            setMessages((current) => [
              ...current,
              { role: "user", content: userMessage },
              { role: "assistant", content: analysis.reply_draft },
            ]);
            setResult(analysis);
            setDraft("");
            setRefreshToken((current) => current + 1);
            setLiveRunStatus("success");
            stopProgressTracking();
            setIsAnalyzing(false);
            resolve(analysis);
          },
          onError: (message) => {
            setErrorMessage(message);
            setLiveRunStatus("failed");
            stopProgressTracking();
            setIsAnalyzing(false);
            reject(new Error(message));
          },
        });
      });
    } catch (error) {
      const mismatch = getSessionOrderMismatch(error);
      if (mismatch) {
        setSessionOrderMismatch(mismatch);
        setErrorMessage(null);
        setLiveRunStatus(null);
        setActiveRunId(null);
        setLiveSteps([]);
      } else if ((error as { response?: unknown }).response) {
        setErrorMessage(getAnalysisErrorMessage(error));
        setLiveRunStatus(null);
        setActiveRunId(null);
        setLiveSteps([]);
      }
    } finally {
      setIsAnalyzing(false);
    }
  }, [draft, isAnalyzing, messages, sessionId, stopProgressTracking]);

  const startNewConversation = useCallback(() => {
    if (isAnalyzing) return;
    stopProgressTracking();
    setSessionId(makeSessionId());
    setMessages([]);
    if (sessionOrderMismatch === null) setDraft("");
    setResult(null);
    setErrorMessage(null);
    setSessionOrderMismatch(null);
    setActiveRunId(null);
    setLiveRunStatus(null);
    setLiveSteps([]);
  }, [isAnalyzing, sessionOrderMismatch, stopProgressTracking]);

  const value = useMemo(() => ({
    sessionId,
    messages,
    draft,
    result,
    errorMessage,
    sessionOrderMismatch,
    isAnalyzing,
    refreshToken,
    activeRunId,
    liveRunStatus,
    liveSteps,
    setDraft,
    analyze,
    startNewConversation,
  }), [activeRunId, analyze, draft, errorMessage, isAnalyzing, liveRunStatus, liveSteps, messages, refreshToken, result, sessionId, sessionOrderMismatch, startNewConversation]);

  return <CopilotAnalysisContext.Provider value={value}>{children}</CopilotAnalysisContext.Provider>;
}

export function useCopilotAnalysis() {
  const context = useContext(CopilotAnalysisContext);
  if (!context) throw new Error("useCopilotAnalysis must be used within CopilotAnalysisProvider");
  return context;
}
