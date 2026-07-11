from pydantic import BaseModel, Field


class ReportRequest(BaseModel):
    session_id: str = Field(default="sess_demo")
    dataset_id: str | None = None


class ReportResponse(BaseModel):
    session_id: str
    report_markdown: str
