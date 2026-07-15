import { createContext, useCallback, useContext, useMemo, useState } from "react";

import { analyzeCopilot } from "./services/api";
import type { CopilotAnalyzeResponse } from "./services/api";

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
  isAnalyzing: boolean;
  refreshToken: number;
  setDraft: (draft: string) => void;
  analyze: () => Promise<void>;
  startNewConversation: () => void;
};

const CopilotAnalysisContext = createContext<CopilotAnalysisContextValue | null>(null);

function makeSessionId() {
  return `WEB-${Date.now()}`;
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
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);

  const analyze = useCallback(async () => {
    const userMessage = draft.trim();
    if (!userMessage || isAnalyzing) return;

    setIsAnalyzing(true);
    setErrorMessage(null);
    try {
      const analysis = await analyzeCopilot({
        session_id: sessionId,
        user_id: "客服A",
        user_message: userMessage,
        history: messages.slice(-8),
      });
      setMessages((current) => [
        ...current,
        { role: "user", content: userMessage },
        { role: "assistant", content: analysis.reply_draft },
      ]);
      setResult(analysis);
      setDraft("");
      setRefreshToken((current) => current + 1);
    } catch (error) {
      setErrorMessage(getAnalysisErrorMessage(error));
    } finally {
      setIsAnalyzing(false);
    }
  }, [draft, isAnalyzing, messages, sessionId]);

  const startNewConversation = useCallback(() => {
    if (isAnalyzing) return;
    setSessionId(makeSessionId());
    setMessages([]);
    setDraft("");
    setResult(null);
    setErrorMessage(null);
  }, [isAnalyzing]);

  const value = useMemo(() => ({
    sessionId,
    messages,
    draft,
    result,
    errorMessage,
    isAnalyzing,
    refreshToken,
    setDraft,
    analyze,
    startNewConversation,
  }), [analyze, draft, errorMessage, isAnalyzing, messages, refreshToken, result, sessionId, startNewConversation]);

  return <CopilotAnalysisContext.Provider value={value}>{children}</CopilotAnalysisContext.Provider>;
}

export function useCopilotAnalysis() {
  const context = useContext(CopilotAnalysisContext);
  if (!context) throw new Error("useCopilotAnalysis must be used within CopilotAnalysisProvider");
  return context;
}
