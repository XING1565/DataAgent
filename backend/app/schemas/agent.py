from typing import Any

from pydantic import BaseModel, Field

from app.schemas.chat import AgentTraceStep


class AgentEvent(BaseModel):
    event_id: str
    session_id: str = "global"
    dataset_id: str | None = None
    type: str
    title: str
    summary: str
    status: str = "success"
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    trace_steps: list[AgentTraceStep] = Field(default_factory=list)


class AgentEventsResponse(BaseModel):
    events: list[AgentEvent] = Field(default_factory=list)


class AgentStatus(BaseModel):
    status: str
    message: str
    last_event: AgentEvent | None = None
    total_events: int = 0
    warning_count: int = 0
    error_count: int = 0


class AgentTraceResponse(BaseModel):
    session_id: str
    trace_steps: list[AgentTraceStep] = Field(default_factory=list)
