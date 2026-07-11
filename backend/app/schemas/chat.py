from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    dataset_id: str
    message: str
    session_id: str = Field(default="sess_demo")


class ChartArtifact(BaseModel):
    chart_id: str
    type: str
    title: str
    url: str
    status: str = "ok"
    format: str = "png"


class AnalysisResult(BaseModel):
    type: str
    value: Any = None
    summary: str = ""


class AgentTraceStep(BaseModel):
    step: str
    status: str
    duration_ms: int
    observation: str
    action: str
    thought: str = ""
    tool: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    tool_name: str | None = None
    input_summary: str | None = None
    output_summary: str | None = None
    fallback_used: bool = False
    error_message: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    dataset_id: str
    answer: str
    result: AnalysisResult
    charts: list[ChartArtifact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    trace_steps: list[AgentTraceStep] = Field(default_factory=list)
