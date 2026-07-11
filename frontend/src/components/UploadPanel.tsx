import { CheckCircle2, FileSpreadsheet, RefreshCw, Upload } from "lucide-react";
import { useRef, useState } from "react";

import type { DatasetUploadResponse } from "../types/api";

type Props = {
  dataset: DatasetUploadResponse | null;
  uploadedAt: string;
  loading: boolean;
  error: string;
  onUpload: (file: File) => void;
};

export function UploadPanel({ dataset, uploadedAt, loading, error, onUpload }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragging, setDragging] = useState(false);

  function handleFile(file?: File) {
    if (file) onUpload(file);
  }

  return (
    <div className="stack">
      {dataset ? (
        <div className="upload-status">
          <div className="upload-status-top">
            <div className="file-badge">
              <FileSpreadsheet size={22} />
            </div>
            <div className="file-details">
              <div className="file-name">{dataset.filename}</div>
              <div className="file-meta">
                <span>{dataset.rows.toLocaleString()} 行 x {dataset.columns} 列</span>
                <span>上传时间：{uploadedAt || "刚刚"}</span>
              </div>
            </div>
          </div>

          <div className="parse-status">
            <CheckCircle2 size={16} />
            <span>解析成功，已生成字段结构和数据质量摘要</span>
          </div>

          <code className="dataset-id">{dataset.dataset_id}</code>

          <div className="schema-preview">
            <div className="schema-title">字段结构</div>
            <div className="schema-preview-list">
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
          </div>

          <button className="reupload-btn" onClick={() => inputRef.current?.click()} disabled={loading}>
            <RefreshCw size={15} />
            {loading ? "正在上传..." : "重新上传"}
          </button>
        </div>
      ) : (
        <button
          className={dragging ? "upload-zone active" : "upload-zone"}
          onClick={() => inputRef.current?.click()}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            handleFile(event.dataTransfer.files[0]);
          }}
        >
          <Upload size={20} />
          <span>{loading ? "正在上传..." : "上传 CSV / XLSX"}</span>
          <small>拖拽文件到这里，或点击选择文件</small>
          <em>支持 .csv、.xlsx，上传后自动生成字段与质量摘要</em>
        </button>
      )}
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.xlsx"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          handleFile(file);
          event.currentTarget.value = "";
        }}
      />
      {error && <div className="alert error">{error}</div>}
    </div>
  );
}
