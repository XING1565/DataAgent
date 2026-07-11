import { Database, Rows3 } from "lucide-react";

import type { DatasetUploadResponse } from "../types/api";

type Props = {
  dataset: DatasetUploadResponse | null;
};

export function DatasetSummary({ dataset }: Props) {
  if (!dataset) {
    return <div className="empty-state">上传 CSV 或 XLSX 文件后，这里会展示数据规模、字段结构和质量摘要。</div>;
  }

  return (
    <div className="stack">
      <div className="metric-grid">
        <div className="metric">
          <Database size={16} />
          <span>{dataset.rows} 行</span>
        </div>
        <div className="metric">
          <Rows3 size={16} />
          <span>{dataset.columns} 列</span>
        </div>
        <div className="metric">
          <span>{dataset.quality_summary.missing_cells}</span>
          <small>缺失单元格</small>
        </div>
        <div className="metric">
          <span>{dataset.quality_summary.duplicate_rows}</span>
          <small>重复行</small>
        </div>
      </div>

      <div className="section-title">字段结构</div>
      <div className="schema-list">
        {dataset.schema.map((column) => (
          <div className="schema-row" key={column.name}>
            <div>
              <strong>{column.name}</strong>
              <span>{column.dtype}</span>
            </div>
            <small>{Math.round(column.missing_ratio * 10000) / 100}% 缺失</small>
          </div>
        ))}
      </div>
    </div>
  );
}
