from fastapi import APIRouter

from app.schemas.report import ReportRequest, ReportResponse
from app.services.agent_event_store import AgentEventStore
from app.services.jobs_store import JobsStore
from app.services.report_service import ReportService


router = APIRouter(prefix="/reports", tags=["reports"])
report_service = ReportService()
agent_event_store = AgentEventStore()
jobs_store = JobsStore()


@router.post("", response_model=ReportResponse)
def create_report(request: ReportRequest) -> ReportResponse:
    job = jobs_store.create_job(session_id=request.session_id, type="report", message="生成 Markdown 报告")
    jobs_store.update_job(job.id, status="running", progress=20, message="报告生成中。")
    try:
        report_markdown = report_service.generate_markdown(request.session_id, dataset_id=request.dataset_id)
    except Exception as exc:
        jobs_store.update_job(job.id, status="failed", progress=100, message="报告生成失败。", error=str(exc))
        raise
    agent_event_store.append_event(
        type="report_generated",
        title="分析报告已生成",
        summary="已通过报表接口生成 Markdown 报告。",
        status="success",
        session_id=request.session_id,
        dataset_id=request.dataset_id,
        metadata={"markdown_length": len(report_markdown)},
    )
    response = ReportResponse(
        session_id=request.session_id,
        report_markdown=report_markdown,
    )
    jobs_store.update_job(
        job.id,
        status="succeeded",
        progress=100,
        message="报告生成完成。",
        result_json=response.model_dump(),
    )
    return response
