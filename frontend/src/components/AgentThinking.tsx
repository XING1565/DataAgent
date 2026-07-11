import type { AgentTraceStep } from "../types/api";

type Props = {
  active: boolean;
  steps?: AgentTraceStep[];
};

type ThinkingStep = {
  name: string;
  status: "done" | "active" | "pending";
  tool: string;
  duration?: number;
};

const FALLBACK_STEPS: ThinkingStep[] = [
  { name: "理解数据结构", status: "done", tool: "dataset_loader", duration: 120 },
  { name: "规划分析任务", status: "done", tool: "analysis_graph", duration: 86 },
  { name: "执行统计分析", status: "active", tool: "pandasai_agent" },
  { name: "生成图表/表格", status: "pending", tool: "chart_tool" },
  { name: "保存会话与报告", status: "pending", tool: "session_store" },
];

const STEP_LABELS: Record<string, string> = {
  load_dataset: "加载数据集",
  resolve_context: "解析上下文",
  plan_query: "规划 SQL 查询",
  execute_query_tool: "执行 SQL 查询",
  analyze_query_result: "整理查询结果",
  analyze_table_tool: "执行表格分析",
  build_chart_tool: "生成图表",
  export_report_tool: "生成报告",
  save_session: "保存会话",
  finalize: "整理响应",
};

export function AgentThinking({ active, steps }: Props) {
  if (!active) return null;

  const visibleSteps = steps?.length ? steps.map(toThinkingStep) : FALLBACK_STEPS;
  const completedSteps = visibleSteps.filter((step) => step.status === "done").length;

  return (
    <div className="agent-thinking" aria-live="polite">
      <div className="thinking-header">
        <div className="thinking-avatar">AI</div>
        <div className="thinking-info">
          <div className="thinking-title">DataAgent 正在分析</div>
          <div className="thinking-subtitle">
            已执行 {completedSteps}/{visibleSteps.length} 个步骤 · 实时推理中
          </div>
        </div>
        <div className="thinking-spinner" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </div>
      <div className="thinking-steps">
        {visibleSteps.map((step, index) => (
          <div className={`t-step ${step.status}`} key={`${step.name}-${index}`}>
            <div className="t-step-left">
              <div className="t-step-icon">
                {step.status === "done" && "✓"}
                {step.status === "active" && <span className="t-step-pulse" />}
                {step.status === "pending" && "•"}
              </div>
              {index < visibleSteps.length - 1 && <div className="t-step-line" />}
            </div>
            <div className="t-step-content">
              <div className="t-step-name">{step.name}</div>
              <div className="t-step-meta">
                <span className="t-step-tool">@{step.tool}</span>
                {typeof step.duration === "number" && <span className="t-step-time">{step.duration}ms</span>}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function toThinkingStep(step: AgentTraceStep): ThinkingStep {
  return {
    name: STEP_LABELS[step.step] ?? step.step,
    status: step.status === "active" ? "active" : step.status === "skipped" ? "pending" : "done",
    tool: step.tool_name || step.tool || step.step,
    duration: step.status === "active" ? undefined : step.duration_ms,
  };
}
