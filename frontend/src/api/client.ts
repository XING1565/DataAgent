import type {
  AgentEventsResponse,
  AgentStatus,
  AgentTraceResponse,
  ChatRequest,
  ChatResponse,
  ChatStreamEvent,
  DatasetUploadResponse,
  JobEventsResponse,
  JobRecord,
  JobsResponse,
  ReportResponse,
} from "../types/api";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function parseResponse<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = body?.detail ?? `Request failed with status ${response.status}`;
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }
  return body as T;
}

export async function uploadDataset(file: File): Promise<DatasetUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE_URL}/api/v1/datasets`, {
    method: "POST",
    body: formData,
  });
  return parseResponse<DatasetUploadResponse>(response);
}

export async function sendChat(payload: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseResponse<ChatResponse>(response);
}

type ChatStreamHandlers = {
  onEvent?: (event: ChatStreamEvent) => void;
  onResponse?: (response: ChatResponse) => void;
  onError?: (message: string) => void;
  onDone?: () => void;
};

export async function sendChatStream(payload: ChatRequest, handlers: ChatStreamHandlers = {}): Promise<ChatResponse | null> {
  const response = await fetch(`${API_BASE_URL}/api/v1/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok || !response.body) {
    const body = await response.text().catch(() => "");
    throw new Error(body || `Request failed with status ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResponse: ChatResponse | null = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const event = parseSseEvent(part);
      if (!event) continue;
      handlers.onEvent?.(event);
      if (event.type === "response") {
        finalResponse = event.response;
        handlers.onResponse?.(event.response);
      }
      if (event.type === "error") {
        handlers.onError?.(event.message);
      }
      if (event.type === "done") {
        handlers.onDone?.();
      }
    }
  }

  if (buffer.trim()) {
    const event = parseSseEvent(buffer);
    if (event) {
      handlers.onEvent?.(event);
      if (event.type === "response") {
        finalResponse = event.response;
        handlers.onResponse?.(event.response);
      }
      if (event.type === "error") handlers.onError?.(event.message);
      if (event.type === "done") handlers.onDone?.();
    }
  }

  return finalResponse;
}

function parseSseEvent(block: string): ChatStreamEvent | null {
  const data = block
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (!data) return null;
  return JSON.parse(data) as ChatStreamEvent;
}

export async function generateReport(sessionId: string, datasetId?: string): Promise<ReportResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/reports`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, dataset_id: datasetId }),
  });
  return parseResponse<ReportResponse>(response);
}

export async function getJobs(sessionId?: string, limit = 50): Promise<JobsResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (sessionId) params.set("session_id", sessionId);
  const response = await fetch(`${API_BASE_URL}/api/v1/jobs?${params.toString()}`);
  return parseResponse<JobsResponse>(response);
}

export async function getJob(jobId: string): Promise<JobRecord> {
  const response = await fetch(`${API_BASE_URL}/api/v1/jobs/${encodeURIComponent(jobId)}`);
  return parseResponse<JobRecord>(response);
}

export async function getJobEvents(jobId: string): Promise<JobEventsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/jobs/${encodeURIComponent(jobId)}/events`);
  return parseResponse<JobEventsResponse>(response);
}

export async function cancelJob(jobId: string): Promise<JobRecord> {
  const response = await fetch(`${API_BASE_URL}/api/v1/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: "POST",
  });
  return parseResponse<JobRecord>(response);
}

export async function retryJob(jobId: string): Promise<JobRecord> {
  const response = await fetch(`${API_BASE_URL}/api/v1/jobs/${encodeURIComponent(jobId)}/retry`, {
    method: "POST",
  });
  return parseResponse<JobRecord>(response);
}

export async function getAgentStatus(sessionId?: string): Promise<AgentStatus> {
  const search = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  const response = await fetch(`${API_BASE_URL}/api/v1/agent/status${search}`);
  return parseResponse<AgentStatus>(response);
}

export async function getAgentEvents(sessionId?: string, limit = 50): Promise<AgentEventsResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (sessionId) params.set("session_id", sessionId);
  const response = await fetch(`${API_BASE_URL}/api/v1/agent/events?${params.toString()}`);
  return parseResponse<AgentEventsResponse>(response);
}

export async function getAgentTrace(sessionId: string): Promise<AgentTraceResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/agent/sessions/${encodeURIComponent(sessionId)}/trace`);
  return parseResponse<AgentTraceResponse>(response);
}
