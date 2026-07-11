import { BarChart3, Download, FileText, GitBranch, Table2 } from "lucide-react";
import { useMemo, useState } from "react";

import { API_BASE_URL } from "../api/client";
import type { ChatResponse, DatasetUploadResponse } from "../types/api";
import { DataPreviewTable } from "./DataPreviewTable";
import { ReactTraceFlow } from "./ReactTraceFlow";
import { ReportPanel } from "./ReportPanel";

type Props = {
  dataset: DatasetUploadResponse | null;
  latestResponse: ChatResponse | null;
  reportMarkdown: string;
};

const TABS = [
  { key: "Overview", label: "概览" },
  { key: "Chart", label: "图表" },
  { key: "Table", label: "表格" },
  { key: "Trace", label: "Trace" },
  { key: "Report", label: "报告" },
  { key: "Raw", label: "原始数据" },
] as const;
type Tab = (typeof TABS)[number]["key"];

export function ResultPanel({ dataset, latestResponse, reportMarkdown }: Props) {
  const [tab, setTab] = useState<Tab>("Overview");
  const tableRows = useMemo(() => getTableRows(latestResponse), [latestResponse]);
  const qualityScore = useMemo(() => getQualityScore(dataset), [dataset]);
  const columnStats = useMemo(() => getColumnStats(dataset), [dataset]);
  const autoInsights = useMemo(
    () => getAutoInsights(dataset, latestResponse, qualityScore, columnStats),
    [dataset, latestResponse, qualityScore, columnStats],
  );

  return (
    <div className="result-panel">
      <div className="tabs">
        {TABS.map((item) => (
          <button className={tab === item.key ? "active" : ""} key={item.key} onClick={() => setTab(item.key)}>
            {item.key === "Chart" && <BarChart3 size={14} />}
            {item.key === "Table" && <Table2 size={14} />}
            {item.key === "Trace" && <GitBranch size={14} />}
            {item.key === "Report" && <FileText size={14} />}
            {item.label}
          </button>
        ))}
      </div>

      <div className="result-body">
        {tab === "Overview" && (
          <div className="overview-panel">
            {dataset ? (
              <>
                <div className="insight-grid">
                  <div className="insight-card">
                    <span>数据规模</span>
                    <strong>{dataset.rows.toLocaleString()} 行</strong>
                    <small>{dataset.columns} 个字段 · {columnStats.dateColumns} 个日期列</small>
                  </div>
                  <div className="insight-card">
                    <span>数据质量</span>
                    <strong>{qualityScore}%</strong>
                    <small>{dataset.quality_summary.missing_cells} 个缺失值 · {dataset.quality_summary.duplicate_rows} 个重复行</small>
                  </div>
                  <div className="insight-card">
                    <span>数值字段</span>
                    <strong>{columnStats.numericColumns} 列</strong>
                    <small>{columnStats.numericNames || "等待 Agent 识别业务指标"}</small>
                  </div>
                </div>

                <div className="overview-section">
                  <div className="section-title">自动发现</div>
                  <div className="auto-insights">
                    {autoInsights.map((insight) => (
                      <div className={`auto-insight ${insight.type}`} key={insight.text}>
                        <span className="auto-insight-icon">{insight.icon}</span>
                        <span>{insight.text}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="overview-section">
                  <div className="section-title">最近分析摘要</div>
                  <div className={latestResponse ? "latest-summary" : "empty-state"}>
                    {latestResponse?.result.summary || "暂无分析结果。可以从中间的快捷问题开始，让 Agent 生成趋势、表格或报告。"}
                  </div>
                </div>
                <div className="overview-section">
                  <div className="section-title">数据预览</div>
                  <DataPreviewTable rows={dataset.preview} compact />
                </div>
                {(latestResponse?.warnings.length || latestResponse?.errors.length) ? (
                  <div className="overview-section">
                    <div className="section-title">风险与降级</div>
                    {latestResponse.warnings.map((warning) => (
                      <div className="alert warning" key={warning}>{warning}</div>
                    ))}
                    {latestResponse.errors.map((error) => (
                      <div className="alert error" key={error}>{error}</div>
                    ))}
                  </div>
                ) : null}
              </>
            ) : (
              <EmptyPanel />
            )}
          </div>
        )}

        {tab === "Chart" && (
          <div className="stack">
            {latestResponse?.charts.length ? (
              latestResponse.charts.map((chart) => (
                <figure className="chart-card" key={chart.chart_id}>
                  <div className="chart-card-header">
                    <figcaption>{chart.title}</figcaption>
                    <a
                      className="download-button"
                      href={`${API_BASE_URL}${chart.url}`}
                      download={`${chart.chart_id}.${getChartFormat(chart)}`}
                    >
                      <Download size={14} />
                      下载图表
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
              <div className="empty-state">暂无图表结果。可以提问“查看月度销售趋势”生成图表。</div>
            )}
          </div>
        )}

        {tab === "Table" && <DataPreviewTable rows={tableRows} compact />}

        {tab === "Trace" && <ReactTraceFlow steps={latestResponse?.trace_steps} />}

        {tab === "Report" && <ReportPanel markdown={reportMarkdown} />}

        {tab === "Raw" && <pre className="raw-json">{JSON.stringify(latestResponse, null, 2)}</pre>}
      </div>
    </div>
  );
}

function EmptyPanel() {
  return (
    <div className="empty-panel">
      <div className="preview-cards">
        <div className="preview-card disabled">
          <div className="preview-icon">📋</div>
          <div className="preview-title">数据概览</div>
          <div className="preview-desc">行数、列数、缺失值分析</div>
        </div>
        <div className="preview-card disabled">
          <div className="preview-icon">📈</div>
          <div className="preview-title">智能图表</div>
          <div className="preview-desc">自动推荐最佳可视化</div>
        </div>
        <div className="preview-card disabled">
          <div className="preview-icon">📝</div>
          <div className="preview-title">分析报告</div>
          <div className="preview-desc">AI 生成洞察与建议</div>
        </div>
      </div>
      <div className="empty-panel-text">
        <div className="empty-icon">📤</div>
        <h4>等待上传数据</h4>
        <p>上传后将自动展示数据质量评分、字段分析和可视化推荐。</p>
      </div>
    </div>
  );
}

function getTableRows(response: ChatResponse | null): Record<string, unknown>[] {
  if (!response) return [];
  if (Array.isArray(response.result.value)) return response.result.value as Record<string, unknown>[];
  if (response.result.type === "chart" && Array.isArray(response.result.value)) return response.result.value as Record<string, unknown>[];
  return [];
}

function isHtmlChart(chart: { format?: string; url: string }) {
  return chart.format === "html" || chart.url.toLowerCase().endsWith(".html");
}

function getChartFormat(chart: { format?: string; url: string }) {
  if (chart.format) return chart.format;
  return chart.url.toLowerCase().endsWith(".html") ? "html" : "png";
}

function getQualityScore(dataset: DatasetUploadResponse | null): number {
  if (!dataset || dataset.rows === 0 || dataset.columns === 0) return 0;
  const totalCells = dataset.rows * dataset.columns;
  const missingPenalty = Math.min(60, (dataset.quality_summary.missing_cells / totalCells) * 100);
  const duplicatePenalty = Math.min(40, (dataset.quality_summary.duplicate_rows / dataset.rows) * 100);
  return Math.max(0, Math.round(100 - missingPenalty - duplicatePenalty));
}

function getColumnStats(dataset: DatasetUploadResponse | null) {
  if (!dataset) {
    return { numericColumns: 0, dateColumns: 0, numericNames: "" };
  }

  const numericColumns = dataset.schema.filter((column) =>
    /int|float|double|decimal|number|numeric/i.test(column.dtype),
  );
  const dateColumns = dataset.schema.filter((column) => /date|time|datetime/i.test(column.dtype));

  return {
    numericColumns: numericColumns.length,
    dateColumns: dateColumns.length,
    numericNames: numericColumns.slice(0, 3).map((column) => column.name).join("、"),
  };
}

function getAutoInsights(
  dataset: DatasetUploadResponse | null,
  latestResponse: ChatResponse | null,
  qualityScore: number,
  columnStats: ReturnType<typeof getColumnStats>,
) {
  if (!dataset) return [];

  const insights = [
    {
      type: "quality",
      icon: qualityScore >= 90 ? "✓" : "!",
      text:
        qualityScore >= 90
          ? `数据质量良好，当前评分 ${qualityScore}%，适合直接进入分析。`
          : `数据质量评分 ${qualityScore}%，建议关注缺失值和重复行。`,
    },
    {
      type: "schema",
      icon: "#",
      text: `已识别 ${dataset.columns} 个字段，其中 ${columnStats.numericColumns} 个数值字段、${columnStats.dateColumns} 个日期字段。`,
    },
  ];

  if (latestResponse?.charts.length) {
    insights.push({
      type: "chart",
      icon: "↗",
      text: `已生成 ${latestResponse.charts.length} 个可视化图表，可在“图表”页查看并下载 PNG。`,
    });
  } else if (latestResponse) {
    insights.push({
      type: "analysis",
      icon: "AI",
      text: `Agent 已完成本轮分析，结果类型为 ${latestResponse.result.type}。`,
    });
  } else {
    insights.push({
      type: "analysis",
      icon: "AI",
      text: "可以点击“查看月度销售趋势”触发图表分析，或直接输入业务问题。",
    });
  }

  if (latestResponse?.warnings.length || latestResponse?.errors.length) {
    insights.push({
      type: "risk",
      icon: "!",
      text: `本轮分析记录 ${latestResponse.warnings.length} 个警告、${latestResponse.errors.length} 个错误，已在下方展示。`,
    });
  }

  return insights;
}
