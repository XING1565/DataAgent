import { CheckCircle2, Database, FileSpreadsheet, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";

import type { DatasetUploadResponse } from "../types/api";
import { DataPreviewTable } from "./DataPreviewTable";

type Props = {
  dataset: DatasetUploadResponse | null;
};

export function DataCollectionPanel({ dataset }: Props) {
  const qualityScore = getQualityScore(dataset);

  return (
    <div className="module-page">
      <div className="module-head">
        <div>
          <p className="eyebrow">接入、识别、校验</p>
          <h2>数据采集</h2>
        </div>
        <span className="status-pill">{dataset ? "已接入真实数据" : "等待上传"}</span>
      </div>

      <div className="pipeline-row">
        <PipelineStep icon={<FileSpreadsheet size={16} />} title="上传文件" detail={dataset?.filename ?? "CSV / XLSX"} done={Boolean(dataset)} />
        <PipelineStep icon={<Database size={16} />} title="字段识别" detail={dataset ? `${dataset.schema.length} 个字段` : "自动识别类型"} done={Boolean(dataset)} />
        <PipelineStep icon={<ShieldCheck size={16} />} title="质量校验" detail={dataset ? `${qualityScore}% 评分` : "缺失与重复检测"} done={Boolean(dataset)} />
      </div>

      {dataset ? (
        <>
          <div className="dashboard-metrics">
            <Metric label="数据规模" value={`${dataset.rows.toLocaleString()} 行`} detail={`${dataset.columns} 个字段`} />
            <Metric label="质量评分" value={`${qualityScore}%`} detail={`${dataset.quality_summary.missing_cells} 缺失 · ${dataset.quality_summary.duplicate_rows} 重复`} />
            <Metric label="内存占用" value={formatBytes(dataset.quality_summary.memory_usage_bytes)} detail="Pandas 估算" />
          </div>

          <section className="module-section">
            <div className="section-title">字段结构</div>
            <div className="schema-preview-list expanded">
              {dataset.schema.map((column) => (
                <div className="schema-preview-item" key={column.name}>
                  <span className="schema-name" title={column.name}>{column.name}</span>
                  <span className="schema-type">{column.dtype}</span>
                  <span className={column.missing_count > 0 ? "schema-null warning" : "schema-null good"}>
                    {column.missing_count > 0 ? `${column.missing_count} 缺失` : "完整"}
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="module-section">
            <div className="section-title">数据预览</div>
            <DataPreviewTable rows={dataset.preview} compact />
          </section>
        </>
      ) : (
        <div className="empty-state">请先在左侧上传 CSV 或 XLSX 文件，采集页会展示真实 schema、preview 和 quality summary。</div>
      )}
    </div>
  );
}

function PipelineStep({ icon, title, detail, done }: { icon: ReactNode; title: string; detail: string; done: boolean }) {
  return (
    <div className={`pipeline-step ${done ? "done" : ""}`}>
      <span>{done ? <CheckCircle2 size={16} /> : icon}</span>
      <strong>{title}</strong>
      <small>{detail}</small>
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

function getQualityScore(dataset: DatasetUploadResponse | null): number {
  if (!dataset || dataset.rows === 0 || dataset.columns === 0) return 0;
  const totalCells = dataset.rows * dataset.columns;
  const missingPenalty = Math.min(60, (dataset.quality_summary.missing_cells / totalCells) * 100);
  const duplicatePenalty = Math.min(40, (dataset.quality_summary.duplicate_rows / dataset.rows) * 100);
  return Math.max(0, Math.round(100 - missingPenalty - duplicatePenalty));
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
