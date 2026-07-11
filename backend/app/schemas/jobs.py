from typing import Any

from pydantic import BaseModel, Field


class JobRecord(BaseModel):
    id: str
    session_id: str
    type: str
    status: str
    progress: int = 0
    message: str = ""
    result_json: dict[str, Any] | list[Any] | str | int | float | bool | None = None
    error: str | None = None
    created_at: str
    updated_at: str


class JobEventRecord(BaseModel):
    id: int
    job_id: str
    session_id: str
    sequence: int
    type: str
    payload_json: dict[str, Any] | list[Any] | str | int | float | bool | None = None
    created_at: str


class JobsResponse(BaseModel):
    jobs: list[JobRecord] = Field(default_factory=list)


class JobEventsResponse(BaseModel):
    events: list[JobEventRecord] = Field(default_factory=list)
