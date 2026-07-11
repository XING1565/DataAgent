import { FileText, Send, Sparkles } from "lucide-react";

import type { AgentEvent } from "../types/api";
import { ReportPanel } from "./ReportPanel";

type Props = {
  reportMarkdown: string;
  agentEvents: AgentEvent[];
  onGenerateReport: () => void;
  loading: boolean;
};

const FLOW = [
  { title: "扫描数据", detail: "读取 schema、preview 和历史分析事件。" },
  { title: "提炼结论", detail: "汇总趋势、异常、图表和问答结论。" },
  { title: "输出报告", detail: "生成 Markdown 正文并写入历史事件。" },
];

export function ReportsCenterPanel({ reportMarkdown, agentEvents, onGenerateReport, loading }: Props) {
  const reportEvents = agentEvents.filter((event) => event.type === "report_generated");

  return (
    <div className="module-page">
      <div className="module-head">
        <div>
          <p className="eyebrow">自动生成、审核与沉淀</p>
          <h2>报表中心</h2>
        </div>
        <button className="primary-action" onClick={onGenerateReport} disabled={loading} type="button">
          <Sparkles size={15} />
          {loading ? "生成中..." : "生成报告"}
        </button>
      </div>

      <section className="module-section">
        <div className="section-title">Agent 自动生成流程</div>
        <div className="report-flow">
          {FLOW.map((item, index) => (
            <div className="pipeline-step done" key={item.title}>
              <span>{index + 1}</span>
              <strong>{item.title}</strong>
              <small>{item.detail}</small>
            </div>
          ))}
        </div>
      </section>

      <section className="module-section">
        <div className="section-title">最新报告</div>
        <ReportPanel markdown={reportMarkdown} />
      </section>

      <section className="module-section">
        <div className="section-title">历史报告</div>
        <div className="event-list">
          {reportEvents.length ? (
            reportEvents.map((event) => (
              <div className="event-row success" key={event.event_id}>
                <span className="event-icon"><FileText size={15} /></span>
                <div>
                  <strong>{event.title}</strong>
                  <p>{event.summary}</p>
                </div>
                <time>{formatTime(event.created_at)}</time>
              </div>
            ))
          ) : (
            <div className="empty-state">
              <Send size={18} />
              生成报告后，历史记录会出现在这里。
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false, month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}
