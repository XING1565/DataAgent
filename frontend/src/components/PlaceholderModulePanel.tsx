import { Database, Settings } from "lucide-react";

import type { AgentEvent, DatasetUploadResponse } from "../types/api";

type Props = {
  dataset: DatasetUploadResponse | null;
  agentEvents: AgentEvent[];
};

export function PlaceholderModulePanel({ dataset, agentEvents }: Props) {
  return (
    <div className="module-page">
      <div className="module-head">
        <div>
          <p className="eyebrow">模型、工具、任务与日志配置</p>
          <h2>设置</h2>
        </div>
        <span className="status-pill">演示模块</span>
      </div>

      <div className="placeholder-module">
        <Settings size={22} />
        <div>
          <h3>Agent 能力配置</h3>
          <p>当前启用自然语言分析、SQL 查询、Trace 可观测性、图表生成、报告导出与 Jobs 状态记录能力。</p>
        </div>
      </div>

      <section className="module-section">
        <div className="section-title">配置状态</div>
        <div className="event-list">
          <div className="event-row success">
            <span className="event-icon">
              <Database size={15} />
            </span>
            <div>
              <strong>{dataset?.filename ?? "等待上传数据集"}</strong>
              <p>{dataset ? "质量摘要、字段结构和预览数据已就绪。" : "暂无可分析数据，请先上传 CSV 或 Excel 文件。"}</p>
            </div>
            <time>{dataset ? "Ready" : "Pending"}</time>
          </div>
          <div className="event-row success">
            <span className="event-icon">
              <Settings size={15} />
            </span>
            <div>
              <strong>事件日志</strong>
              <p>当前 Agent event history 共 {agentEvents.length} 条，可用于工作台和报表中心展示。</p>
            </div>
            <time>Active</time>
          </div>
        </div>
      </section>
    </div>
  );
}
