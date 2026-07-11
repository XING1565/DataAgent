import { Activity, AlertTriangle, CheckCircle2 } from "lucide-react";

import type { AgentEvent, AgentStatus, ChatResponse, DatasetUploadResponse } from "../types/api";

type Props = {
  dataset: DatasetUploadResponse | null;
  latestResponse: ChatResponse | null;
  agentEvents: AgentEvent[];
  agentStatus: AgentStatus | null;
  onOpenAnalysis: () => void;
};

const MOCK_EVENTS: AgentEvent[] = [
  {
    event_id: "mock_quality_scan",
    session_id: "global",
    type: "quality_scan",
    title: "数据质量扫描完成",
    summary: "综合评分稳定，等待上传真实数据。",
    status: "success",
    created_at: new Date().toISOString(),
    metadata: {},
    trace_steps: [],
  },
  {
    event_id: "mock_monitor",
    session_id: "global",
    type: "monitoring",
    title: "Agent 正在监控销售数据",
    summary: "发现 1 个可演示异常，等待进一步分析。",
    status: "warning",
    created_at: new Date().toISOString(),
    metadata: {},
    trace_steps: [],
  },
];

export function WorkspacePanel({ dataset, latestResponse, agentEvents, agentStatus, onOpenAnalysis }: Props) {
  const events = agentEvents.length ? agentEvents : MOCK_EVENTS;
  const qualityScore = getQualityScore(dataset);
  const traceCount = latestResponse?.trace_steps.length ?? 0;
  const statusMessage = agentStatus?.message ?? "Agent 正在监控销售数据，等待分析任务。";

  return (
    <div className="module-page">
      <div className="module-head">
        <div>
          <p className="eyebrow">Agent 工作台</p>
          <h2>今日洞察与执行历史</h2>
        </div>
        <button className="primary-action" onClick={onOpenAnalysis} type="button">
          <Activity size={15} />
          智能分析
        </button>
      </div>

      <div className="dashboard-metrics">
        <MetricCard label="数据质量" value={dataset ? `${qualityScore}%` : "待上传"} detail={dataset ? `${dataset.rows} 行 · ${dataset.columns} 列` : "上传后自动评估"} />
        <MetricCard label="今日事件" value={String(events.length)} detail={`${agentStatus?.warning_count ?? 0} 警告 · ${agentStatus?.error_count ?? 0} 错误`} />
        <MetricCard label="最近 Trace" value={traceCount ? `${traceCount} 步` : "Mock"} detail={latestResponse?.result.type ?? "等待分析"} />
      </div>

      <section className="agent-insight-panel">
        <div>
          <span className="agent-badge">Agent 今日洞察</span>
          <h3>{latestResponse ? "最近一次分析已完成" : "主动发现：等待真实分析任务"}</h3>
          <p>{latestResponse?.result.summary || statusMessage}</p>
        </div>
        <div className="agent-note">
          <strong>自动完成</strong>
          <span>{statusMessage}</span>
        </div>
      </section>

      <section className="module-section">
        <div className="section-title">执行历史</div>
        <div className="event-list">
          {events.slice(0, 8).map((event) => (
            <div className={`event-row ${event.status}`} key={event.event_id}>
              <span className="event-icon">{getEventIcon(event.status)}</span>
              <div>
                <strong>{event.title}</strong>
                <p>{event.summary}</p>
              </div>
              <time>{formatTime(event.created_at)}</time>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="workspace-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function getEventIcon(status: string) {
  if (status === "warning") return <AlertTriangle size={15} />;
  if (status === "error") return <AlertTriangle size={15} />;
  return <CheckCircle2 size={15} />;
}

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false, month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function getQualityScore(dataset: DatasetUploadResponse | null): number {
  if (!dataset || dataset.rows === 0 || dataset.columns === 0) return 0;
  const totalCells = dataset.rows * dataset.columns;
  const missingPenalty = Math.min(60, (dataset.quality_summary.missing_cells / totalCells) * 100);
  const duplicatePenalty = Math.min(40, (dataset.quality_summary.duplicate_rows / dataset.rows) * 100);
  return Math.max(0, Math.round(100 - missingPenalty - duplicatePenalty));
}
