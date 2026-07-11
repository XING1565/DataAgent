import { useEffect, useMemo, useState } from "react";

import { getAgentEvents, getAgentStatus, sendChat, sendChatStream, uploadDataset } from "./api/client";
import { ChatPanel } from "./components/ChatPanel";
import { DashboardPanel } from "./components/DashboardPanel";
import { DataCollectionPanel } from "./components/DataCollectionPanel";
import { DatasetSummary } from "./components/DatasetSummary";
import { PlaceholderModulePanel } from "./components/PlaceholderModulePanel";
import { ResultPanel } from "./components/ResultPanel";
import { ReportsCenterPanel } from "./components/ReportsCenterPanel";
import { AppSection, SidebarNavigation } from "./components/SidebarNavigation";
import { TopbarAgentStatus } from "./components/TopbarAgentStatus";
import { UploadPanel } from "./components/UploadPanel";
import { WorkspacePanel } from "./components/WorkspacePanel";
import type {
  AgentEvent,
  AgentStatus,
  AgentTraceStep,
  ChatMessage,
  ChatResponse,
  ChatStreamEvent,
  DatasetUploadResponse,
} from "./types/api";

const SESSION_PREFIX = "sess_ui";
const MIN_THINKING_MS = 1600;

function waitForMinimum(startedAt: number, minimumMs: number) {
  const remaining = minimumMs - (Date.now() - startedAt);
  return remaining > 0 ? new Promise((resolve) => setTimeout(resolve, remaining)) : Promise.resolve();
}

export default function App() {
  const [dataset, setDataset] = useState<DatasetUploadResponse | null>(null);
  const [uploadedAt, setUploadedAt] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [latestResponse, setLatestResponse] = useState<ChatResponse | null>(null);
  const [streamTraceSteps, setStreamTraceSteps] = useState<AgentTraceStep[]>([]);
  const [agentEvents, setAgentEvents] = useState<AgentEvent[]>([]);
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [activeSection, setActiveSection] = useState<AppSection>("workspace");
  const [reportMarkdown, setReportMarkdown] = useState("");
  const [uploading, setUploading] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);
  const [thinkingVisible, setThinkingVisible] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [chatError, setChatError] = useState("");
  const sessionId = useMemo(() => `${SESSION_PREFIX}_${Date.now().toString(36)}`, []);

  async function refreshAgentData() {
    try {
      const [eventsResponse, statusResponse] = await Promise.all([getAgentEvents(undefined, 50), getAgentStatus()]);
      setAgentEvents(eventsResponse.events);
      setAgentStatus(statusResponse);
    } catch {
      setAgentEvents([]);
      setAgentStatus(null);
    }
  }

  useEffect(() => {
    refreshAgentData();
  }, []);

  async function handleUpload(file: File) {
    setUploading(true);
    setUploadError("");
    try {
      const response = await uploadDataset(file);
      setDataset(response);
      setUploadedAt(new Date().toLocaleString("zh-CN", { hour12: false }));
      setMessages([]);
      setLatestResponse(null);
      setStreamTraceSteps([]);
      setReportMarkdown("");
      await refreshAgentData();
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "上传失败，请检查文件格式后重试");
    } finally {
      setUploading(false);
    }
  }

  async function handleSend(message: string) {
    if (!dataset) return;
    const thinkingStartedAt = Date.now();
    setChatLoading(true);
    setThinkingVisible(true);
    setChatError("");
    setStreamTraceSteps([]);
    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: "user", content: message };
    setMessages((current) => [...current, userMessage]);
    try {
      const response = await runChatRequest(message, dataset);
      await waitForMinimum(thinkingStartedAt, MIN_THINKING_MS);
      await commitChatResponse(response, response.answer || response.result.summary);
    } catch (error) {
      await waitForMinimum(thinkingStartedAt, MIN_THINKING_MS);
      const messageText = error instanceof Error ? error.message : "分析失败，请检查模型配置或稍后重试";
      setChatError(messageText);
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", content: messageText }]);
    } finally {
      setThinkingVisible(false);
      setChatLoading(false);
      setStreamTraceSteps([]);
    }
  }

  async function handleGenerateReport() {
    if (!dataset) return;
    const thinkingStartedAt = Date.now();
    setChatLoading(true);
    setThinkingVisible(true);
    setChatError("");
    const message = "生成分析报告";
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content: message }]);
    try {
      const response = await runChatRequest(message, dataset);
      await waitForMinimum(thinkingStartedAt, MIN_THINKING_MS);
      setLatestResponse(response);
      await refreshAgentData();
      if (typeof response.result.value === "string") {
        setReportMarkdown(response.result.value);
      }
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "分析报告已生成，可在右侧“报告”页查看和复制。",
          response,
        },
      ]);
    } catch (error) {
      await waitForMinimum(thinkingStartedAt, MIN_THINKING_MS);
      setChatError(error instanceof Error ? error.message : "报告生成失败，请稍后重试");
    } finally {
      setThinkingVisible(false);
      setChatLoading(false);
      setStreamTraceSteps([]);
    }
  }

  async function runChatRequest(message: string, currentDataset: DatasetUploadResponse): Promise<ChatResponse> {
    const payload = { session_id: sessionId, dataset_id: currentDataset.dataset_id, message };
    try {
      const streamedResponse = await sendChatStream(payload, {
        onEvent: (event) => handleChatStreamEvent(event, payload),
        onResponse: (response) => {
          setLatestResponse(response);
          if (response.result.type === "markdown" && typeof response.result.value === "string") {
            setReportMarkdown(response.result.value);
          }
        },
        onError: (messageText) => setChatError(messageText),
      });
      if (streamedResponse) return streamedResponse;
    } catch {
      setStreamTraceSteps([]);
    }
    return sendChat(payload);
  }

  async function commitChatResponse(response: ChatResponse, content: string) {
    setLatestResponse(response);
    await refreshAgentData();
    if (response.result.type === "markdown" && typeof response.result.value === "string") {
      setReportMarkdown(response.result.value);
    }
    setMessages((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        role: "assistant",
        content,
        response,
      },
    ]);
  }

  function handleChatStreamEvent(
    event: ChatStreamEvent,
    payload: { session_id: string; dataset_id: string; message: string },
  ) {
    if (event.type === "step_started") {
      updateStreamingTrace(payload, (steps) => [
        ...steps.filter((step) => step.step !== event.step || step.status !== "active"),
        {
          step: event.step,
          status: "active",
          duration_ms: 0,
          observation: event.message,
          action: "running",
          thought: "",
          tool: "",
          details: {},
          fallback_used: false,
        },
      ]);
      return;
    }
    if (event.type === "step_finished") {
      updateStreamingTrace(payload, (steps) => [
        ...steps.filter((step) => !(step.step === event.step && step.status === "active")),
        event.trace_step,
      ]);
      return;
    }
    if (event.type === "response") {
      setLatestResponse(event.response);
    }
  }

  function updateStreamingTrace(
    payload: { session_id: string; dataset_id: string; message: string },
    updater: (steps: AgentTraceStep[]) => AgentTraceStep[],
  ) {
    setStreamTraceSteps((current) => {
      const next = updater(current);
      setLatestResponse((response) => {
        if (response && response.dataset_id === payload.dataset_id && response.session_id === payload.session_id && response.result.type !== "text") {
          return { ...response, trace_steps: next };
        }
        return {
          session_id: payload.session_id,
          dataset_id: payload.dataset_id,
          answer: "分析进行中...",
          result: { type: "text", value: null, summary: "分析进行中..." },
          charts: [],
          warnings: [],
          errors: [],
          trace_steps: next,
        };
      });
      return next;
    });
  }

  return (
    <main className="app-shell">
      <aside className="panel sidebar">
        <div className="sidebar-header">
          <div className="brand-logo">DA</div>
          <div>
            <p className="brand-subtitle">DataAgent</p>
            <h1 className="brand-title">数据分析工作台</h1>
            <span className="brand-tag">数据分析 Agent</span>
          </div>
        </div>
        <UploadPanel dataset={dataset} uploadedAt={uploadedAt} loading={uploading} error={uploadError} onUpload={handleUpload} />
        <SidebarNavigation activeSection={activeSection} onChange={setActiveSection} />
        {!dataset && <DatasetSummary dataset={dataset} />}
      </aside>

      <section className="panel center">
        <div className="panel-header">
          <div>
            <p className="eyebrow">{getSectionEyebrow(activeSection)}</p>
            <h2>{dataset ? `当前会话：${sessionId}` : getSectionTitle(activeSection)}</h2>
          </div>
          {chatError && <div className="alert error">{chatError}</div>}
        </div>
        <TopbarAgentStatus latestResponse={latestResponse} loading={chatLoading} agentEvents={agentEvents} />
        {activeSection === "workspace" && (
          <WorkspacePanel
            dataset={dataset}
            latestResponse={latestResponse}
            agentEvents={agentEvents}
            agentStatus={agentStatus}
            onOpenAnalysis={() => setActiveSection("analysis")}
          />
        )}
        {activeSection === "collection" && <DataCollectionPanel dataset={dataset} />}
        {activeSection === "analysis" && (
          <ChatPanel
            disabled={!dataset}
            loading={chatLoading}
            thinkingVisible={thinkingVisible}
            thinkingSteps={streamTraceSteps}
            messages={messages}
            onSend={handleSend}
            onGenerateReport={handleGenerateReport}
          />
        )}
        {activeSection === "dashboard" && <DashboardPanel dataset={dataset} latestResponse={latestResponse} />}
        {activeSection === "reports" && (
          <ReportsCenterPanel
            reportMarkdown={reportMarkdown}
            agentEvents={agentEvents}
            onGenerateReport={handleGenerateReport}
            loading={chatLoading}
          />
        )}
        {activeSection === "settings" && <PlaceholderModulePanel dataset={dataset} agentEvents={agentEvents} />}
      </section>

      <section className="panel right">
        <ResultPanel dataset={dataset} latestResponse={latestResponse} reportMarkdown={reportMarkdown} />
      </section>
    </main>
  );
}

function getSectionEyebrow(section: AppSection) {
  const labels: Record<AppSection, string> = {
    workspace: "Agent 工作台",
    collection: "数据采集",
    analysis: "智能分析对话",
    dashboard: "数据看板",
    reports: "报表中心",
    settings: "设置",
  };
  return labels[section];
}

function getSectionTitle(section: AppSection) {
  const labels: Record<AppSection, string> = {
    workspace: "今日洞察与执行历史",
    collection: "请先上传数据集",
    analysis: "请先上传数据集",
    dashboard: "等待数据看板数据",
    reports: "等待生成报告",
    settings: "Agent 配置状态",
  };
  return labels[section];
}
