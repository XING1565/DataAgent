export type ColumnSchema = {
  name: string;
  dtype: string;
  non_null_count: number;
  missing_count: number;
  missing_ratio: number;
};

export type QualitySummary = {
  missing_cells: number;
  duplicate_rows: number;
  memory_usage_bytes: number;
};

export type DatasetUploadResponse = {
  dataset_id: string;
  filename: string;
  rows: number;
  columns: number;
  schema: ColumnSchema[];
  preview: Record<string, unknown>[];
  quality_summary: QualitySummary;
};

export type ChartArtifact = {
  chart_id: string;
  type: string;
  title: string;
  url: string;
  status: string;
  format?: "html" | "png" | string;
};

export type AnalysisResult = {
  type: "text" | "number" | "dataframe" | "chart" | "markdown" | "error" | string;
  value: unknown;
  summary: string;
};

export type AgentTraceStep = {
  step: string;
  status: "success" | "warning" | "error" | "skipped" | string;
  duration_ms: number;
  observation: string;
  action: string;
  thought?: string;
  tool?: string;
  details?: Record<string, unknown>;
  tool_name?: string | null;
  input_summary?: string | null;
  output_summary?: string | null;
  fallback_used?: boolean;
  error_message?: string | null;
};

export type ChatRequest = {
  session_id: string;
  dataset_id: string;
  message: string;
};

export type ChatResponse = {
  session_id: string;
  dataset_id: string;
  answer: string;
  result: AnalysisResult;
  charts: ChartArtifact[];
  warnings: string[];
  errors: string[];
  trace_steps: AgentTraceStep[];
};

export type ChatStreamEvent =
  | { type: "step_started"; step: string; message: string }
  | { type: "step_finished"; step: string; status: string; duration_ms: number; trace_step: AgentTraceStep }
  | { type: "text"; content: string }
  | { type: "chart"; chart: ChartArtifact }
  | { type: "response"; response: ChatResponse }
  | { type: "error"; message: string }
  | { type: "done" };

export type ReportResponse = {
  session_id: string;
  report_markdown: string;
};

export type JobRecord = {
  id: string;
  session_id: string;
  type: string;
  status: string;
  progress: number;
  message: string;
  result_json: unknown;
  error?: string | null;
  created_at: string;
  updated_at: string;
};

export type JobEventRecord = {
  id: number;
  job_id: string;
  session_id: string;
  sequence: number;
  type: string;
  payload_json: unknown;
  created_at: string;
};

export type JobsResponse = {
  jobs: JobRecord[];
};

export type JobEventsResponse = {
  events: JobEventRecord[];
};

export type AgentEvent = {
  event_id: string;
  session_id: string;
  dataset_id?: string | null;
  type: string;
  title: string;
  summary: string;
  status: "success" | "warning" | "error" | "idle" | string;
  created_at: string;
  metadata: Record<string, unknown>;
  trace_steps: AgentTraceStep[];
};

export type AgentEventsResponse = {
  events: AgentEvent[];
};

export type AgentStatus = {
  status: "success" | "warning" | "error" | "idle" | string;
  message: string;
  last_event?: AgentEvent | null;
  total_events: number;
  warning_count: number;
  error_count: number;
};

export type AgentTraceResponse = {
  session_id: string;
  trace_steps: AgentTraceStep[];
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  response?: ChatResponse;
};
