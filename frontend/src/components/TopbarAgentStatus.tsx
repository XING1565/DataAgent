import { Activity, AlertTriangle, CheckCircle2, Clock3 } from "lucide-react";
import { useState } from "react";

import type { AgentEvent, ChatResponse } from "../types/api";

type Props = {
  latestResponse: ChatResponse | null;
  loading: boolean;
  agentEvents?: AgentEvent[];
};

const MOCK_LOGS = [
  "等待用户上传数据或发起智能分析任务。",
  "Trace、预警和报告事件会写入 Agent history。",
  "Tool Trace 会展示参数摘要、耗时、状态和 fallback。",
];

const STEP_NAMES: Record<string, string> = {
  load_dataset: "加载数据",
  resolve_context: "解析上下文",
  pandasai_analysis: "智能分析",
  visualize_or_fallback: "图表生成",
  analyze_table_tool: "分析工具",
  build_chart_tool: "图表工具",
  export_report_tool: "报告工具",
  save_session: "保存会话",
  finalize: "整理响应",
  generate_report: "生成报告",
};

export function TopbarAgentStatus({ latestResponse, loading, agentEvents = [] }: Props) {
  const [open, setOpen] = useState(false);
  const traceSteps = latestResponse?.trace_steps ?? [];
  const hasTrace = traceSteps.length > 0;
  const totalDuration = traceSteps.reduce((sum, step) => sum + Math.max(0, step.duration_ms || 0), 0);
  const errorCount = latestResponse?.errors.length ?? 0;
  const warningCount = latestResponse?.warnings.length ?? 0;
  const lastStep = traceSteps[traceSteps.length - 1];
  const stateText = loading
    ? "Agent 状态：正在分析数据"
    : hasTrace
      ? `Agent 状态：最近完成 ${formatStepName(lastStep.step)}`
      : "Agent 状态：正在监控数据 / 等待分析任务";

  return (
    <div className="agent-status-wrap">
      <button
        className={`agent-status-bar ${loading ? "active" : hasTrace ? lastStep.status : "idle"}`}
        onClick={() => setOpen((current) => !current)}
        type="button"
      >
        <div className="agent-status-main">
          <span className="agent-status-icon">{errorCount ? <AlertTriangle size={15} /> : <Activity size={15} />}</span>
          <strong>{stateText}</strong>
        </div>
        <div className="agent-status-meta">
          <span>
            <CheckCircle2 size={13} />
            {hasTrace ? `${traceSteps.length} 步` : "Mock"}
          </span>
          <span>
            <Clock3 size={13} />
            {hasTrace ? `${totalDuration} ms` : "待命"}
          </span>
          <span>
            {warningCount} 警告 / {errorCount} 错误
          </span>
        </div>
      </button>
      <div className={open ? "agent-log-drawer open" : "agent-log-drawer"}>
        <div className="section-title">Agent 实时工作日志</div>
        <div className="agent-log-list">
          {agentEvents.length
            ? agentEvents.slice(0, 5).map((event) => (
                <div className="agent-log-row" key={event.event_id}>
                  <time>{formatTime(event.created_at)}</time>
                  <span>
                    {event.title} / {event.summary}
                  </span>
                </div>
              ))
            : MOCK_LOGS.map((log, index) => (
                <div className="agent-log-row" key={log}>
                  <time>{index === 0 ? "现在" : `T-${index}`}</time>
                  <span>{log}</span>
                </div>
              ))}
        </div>
      </div>
    </div>
  );
}

function formatStepName(step?: string) {
  return step ? STEP_NAMES[step] ?? step : "分析任务";
}

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false, hour: "2-digit", minute: "2-digit" });
}
