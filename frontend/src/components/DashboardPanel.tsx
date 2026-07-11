import { BarChart3, Download, MessageSquareText, Table2 } from "lucide-react";

import { API_BASE_URL } from "../api/client";
import type { ChatResponse, DatasetUploadResponse } from "../types/api";
import { DataPreviewTable } from "./DataPreviewTable";

type Props = {
  dataset: DatasetUploadResponse | null;
  latestResponse: ChatResponse | null;
};

export function DashboardPanel({ dataset, latestResponse }: Props) {
  const numericColumns = dataset?.schema.filter((column) => /int|float|double|decimal|number|numeric/i.test(column.dtype)) ?? [];
  const rows = getTableRows(latestResponse) || dataset?.preview || [];
  const agentRead = getAgentRead(latestResponse, dataset);

  return (
    <div className="module-page">
      <div className="module-head">
        <div>
          <p className="eyebrow">多维指标监控</p>
          <h2>数据看板</h2>
        </div>
        <span className="status-pill">{dataset ? dataset.filename : "等待数据"}</span>
      </div>

      <div className="dashboard-metrics">
        <Metric label="记录数" value={dataset ? dataset.rows.toLocaleString() : "--"} detail="当前数据集" />
        <Metric label="数值字段" value={String(numericColumns.length)} detail={numericColumns.slice(0, 2).map((item) => item.name).join("、") || "等待识别"} />
        <Metric label="图表产物" value={String(latestResponse?.charts.length ?? 0)} detail={latestResponse?.result.type ?? "暂无分析"} />
      </div>

      <section className="module-section">
        <div className="chart-read-head">
          <div className="section-title">图表与 Agent 解读</div>
          <span>
            <MessageSquareText size={14} />
            自动解读
          </span>
        </div>
        <div className="dashboard-chart-grid">
          <div className="dashboard-chart-box">
            {latestResponse?.charts.length ? (
              latestResponse.charts.map((chart) => (
                <figure className="chart-card" key={chart.chart_id}>
                  <div className="chart-card-header">
                    <figcaption>{chart.title}</figcaption>
                    <a className="download-button" href={`${API_BASE_URL}${chart.url}`} download={`${chart.chart_id}.${getChartFormat(chart)}`}>
                      <Download size={14} />
                      下载
                    </a>
                  </div>
                  {isHtmlChart(chart) ? (
                    <iframe className="chart-frame" src={`${API_BASE_URL}${chart.url}`} title={chart.title} />
                  ) : (
                    <img src={`${API_BASE_URL}${chart.url}`} alt={chart.title} />
                  )}
                </figure>
              ))
            ) : (
              <div className="empty-state">
                <BarChart3 size={18} />
                提问“查看月度销售趋势”后，这里会展示生成的图表。
              </div>
            )}
          </div>
          <div className="agent-read-panel">
            <strong>Agent 解读</strong>
            <p>{agentRead}</p>
            <small>{latestResponse ? `结果类型：${latestResponse.result.type}` : "使用最近一次分析结果生成"}</small>
          </div>
        </div>
      </section>

      <section className="module-section">
        <div className="chart-read-head">
          <div className="section-title">明细数据</div>
          <span>
            <Table2 size={14} />
            {rows.length} 行预览
          </span>
        </div>
        <DataPreviewTable rows={rows} compact />
      </section>
    </div>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="workspace-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function getTableRows(response: ChatResponse | null): Record<string, unknown>[] {
  if (!response) return [];
  if (Array.isArray(response.result.value)) return response.result.value as Record<string, unknown>[];
  return [];
}

function isHtmlChart(chart: { format?: string; url: string }) {
  return chart.format === "html" || chart.url.toLowerCase().endsWith(".html");
}

function getChartFormat(chart: { format?: string; url: string }) {
  if (chart.format) return chart.format;
  return chart.url.toLowerCase().endsWith(".html") ? "html" : "png";
}

function getAgentRead(response: ChatResponse | null, dataset: DatasetUploadResponse | null) {
  if (response?.result.summary) return response.result.summary;
  if (dataset) {
    return `已接入 ${dataset.rows.toLocaleString()} 行、${dataset.columns} 列数据。建议先分析趋势、Top 项和异常波动，再生成报表沉淀结论。`;
  }
  return "暂无真实数据，上传数据集后 Agent 会基于 schema、preview 和最近分析结果生成图表解读。";
}
