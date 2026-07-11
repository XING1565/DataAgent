import { CheckCircle2, CircleDashed, Clock3, TriangleAlert, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { AgentTraceStep } from "../types/api";

type Props = {
  steps?: AgentTraceStep[];
};

const MOCK_TRACE_STEPS: AgentTraceStep[] = [
  {
    step: "monitor_dataset",
    status: "success",
    duration_ms: 18,
    observation: "Agent is monitoring the dataset and waiting for an analysis task.",
    thought: "Keep the workspace observable before the user asks a question.",
    action: "standby and monitor",
    tool: "MockAgentStatus",
    details: { mode: "fallback" },
  },
  {
    step: "ready_for_question",
    status: "skipped",
    duration_ms: 0,
    observation: "No recent real trace is available.",
    thought: "Use demo data as an empty-state placeholder.",
    action: "show fallback trace",
    details: { source: "frontend_mock" },
  },
];

const STEP_LABELS: Record<string, string> = {
  detect_command: "识别命令",
  dataset_overview_tool: "数据概况",
  data_cleaning_tool: "清洗建议",
  plan_query: "SQL 规划",
  execute_query_tool: "SQL 查询",
  analyze_query_result: "查询整理",
  load_dataset: "加载数据",
  resolve_context: "解析上下文",
  pandasai_analysis: "智能分析",
  visualize_or_fallback: "图表/降级",
  analyze_table_tool: "分析工具",
  build_chart_tool: "图表工具",
  export_report_tool: "报告工具",
  save_session: "保存会话",
  finalize: "整理响应",
  generate_report: "生成报告",
  monitor_dataset: "监控数据",
  ready_for_question: "等待提问",
};

const STATUS_LABELS: Record<string, string> = {
  success: "完成",
  warning: "警告",
  error: "失败",
  skipped: "跳过",
};

export function ReactTraceFlow({ steps }: Props) {
  const visibleSteps = steps?.length ? steps : MOCK_TRACE_STEPS;
  const [selectedStep, setSelectedStep] = useState(visibleSteps[visibleSteps.length - 1]);
  const selected = visibleSteps.find((step) => step.step === selectedStep.step) ?? visibleSteps[visibleSteps.length - 1];
  const totalDuration = useMemo(
    () => visibleSteps.reduce((sum, step) => sum + Math.max(0, step.duration_ms || 0), 0),
    [visibleSteps],
  );

  useEffect(() => {
    setSelectedStep(visibleSteps[visibleSteps.length - 1]);
  }, [visibleSteps]);

  return (
    <div className="trace-flow">
      <div className="trace-flow-header">
        <div>
          <div className="section-title">ReAct Trace</div>
          <p>Observation / Thought / Action</p>
        </div>
        <span className="trace-duration">
          <Clock3 size={13} />
          {totalDuration} ms
        </span>
      </div>

      <div className="trace-rail" role="list" aria-label="Agent trace steps">
        {visibleSteps.map((step, index) => (
          <button
            className={`trace-node ${step.status} ${selected.step === step.step ? "active" : ""}`}
            key={`${step.step}-${index}`}
            onClick={() => setSelectedStep(step)}
            type="button"
          >
            <span className="trace-node-icon">{getStatusIcon(step.status)}</span>
            <span className="trace-node-main">
              <strong>{STEP_LABELS[step.step] ?? step.step}</strong>
              <small>
                {STATUS_LABELS[step.status] ?? step.status} / {step.duration_ms} ms
              </small>
            </span>
          </button>
        ))}
      </div>

      <div className={`trace-detail ${selected.status}`}>
        <div className="trace-detail-top">
          <div>
            <span>{STATUS_LABELS[selected.status] ?? selected.status}</span>
            <h3>{STEP_LABELS[selected.step] ?? selected.step}</h3>
          </div>
          {(selected.tool_name || selected.tool) && <code>{selected.tool_name || selected.tool}</code>}
        </div>
        <TraceBlock title="Observation" value={selected.observation} />
        {selected.thought && <TraceBlock title="Thought" value={selected.thought} />}
        <TraceBlock title="Action" value={selected.action} />
        <ToolTraceBlock step={selected} />
        {selected.details && Object.keys(selected.details).length > 0 && (
          <pre className="trace-details">{JSON.stringify(selected.details, null, 2)}</pre>
        )}
      </div>
    </div>
  );
}

function TraceBlock({ title, value }: { title: string; value: string }) {
  return (
    <div className="trace-block">
      <span>{title}</span>
      <p>{value}</p>
    </div>
  );
}

function ToolTraceBlock({ step }: { step: AgentTraceStep }) {
  const hasToolTrace =
    step.tool_name ||
    step.input_summary ||
    step.output_summary ||
    step.fallback_used ||
    step.error_message;

  if (!hasToolTrace) return null;

  return (
    <div className="trace-block">
      <span>Tool Trace</span>
      <dl className="tool-trace-list">
        {step.tool_name && (
          <>
            <dt>Tool</dt>
            <dd>{step.tool_name}</dd>
          </>
        )}
        {step.input_summary && (
          <>
            <dt>Input</dt>
            <dd>{step.input_summary}</dd>
          </>
        )}
        {step.output_summary && (
          <>
            <dt>Output</dt>
            <dd>{step.output_summary}</dd>
          </>
        )}
        <dt>Fallback</dt>
        <dd>{step.fallback_used ? "used" : "not used"}</dd>
        {step.error_message && (
          <>
            <dt>Error</dt>
            <dd>{step.error_message}</dd>
          </>
        )}
      </dl>
    </div>
  );
}

function getStatusIcon(status: string) {
  if (status === "success") return <CheckCircle2 size={15} />;
  if (status === "warning") return <TriangleAlert size={15} />;
  if (status === "error") return <XCircle size={15} />;
  return <CircleDashed size={15} />;
}
