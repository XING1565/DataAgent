import json
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.graph.analysis_graph import AnalysisGraph
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.agent_event_store import AgentEventStore
from app.services.jobs_store import JobsStore


router = APIRouter(prefix="/chat", tags=["chat"])
analysis_graph = AnalysisGraph()
agent_event_store = AgentEventStore()
jobs_store = JobsStore()


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    job = jobs_store.create_job(session_id=request.session_id, type="analysis", message=request.message)
    jobs_store.update_job(job.id, status="running", progress=10, message="分析任务执行中。")
    response = analysis_graph.run(
        session_id=request.session_id,
        dataset_id=request.dataset_id,
        message=request.message,
    )
    _record_chat_events(request, response)
    jobs_store.update_job(
        job.id,
        status="failed" if response.errors else "succeeded",
        progress=100,
        message=response.answer or response.result.summary,
        result_json=response.model_dump(),
        error=response.errors[-1] if response.errors else None,
    )
    return response


@router.post("/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    def event_stream() -> Iterator[str]:
        job = jobs_store.create_job(session_id=request.session_id, type="analysis", message=request.message)
        jobs_store.update_job(job.id, status="running", progress=5, message="流式分析任务执行中。")
        for event in analysis_graph.stream(
            session_id=request.session_id,
            dataset_id=request.dataset_id,
            message=request.message,
        ):
            jobs_store.append_event(job.id, session_id=request.session_id, type=str(event.get("type", "event")), payload=event)
            if event.get("type") == "step_finished":
                jobs_store.update_job(
                    job.id,
                    status="running",
                    progress=min(95, jobs_store.get_job(job.id).progress + 10),
                    message=f"已完成步骤：{event.get('step')}",
                    append_event=False,
                )
            if event.get("type") == "response":
                response = ChatResponse.model_validate(event["response"])
                _record_chat_events(request, response)
                jobs_store.update_job(
                    job.id,
                    status="failed" if response.errors else "succeeded",
                    progress=100,
                    message=response.answer or response.result.summary,
                    result_json=response.model_dump(),
                    error=response.errors[-1] if response.errors else None,
                )
            if event.get("type") == "error":
                jobs_store.update_job(
                    job.id,
                    status="failed",
                    progress=100,
                    message=str(event.get("message", "流式分析失败。")),
                    error=str(event.get("message", "流式分析失败。")),
                )
            yield _format_sse(event)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _format_sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _record_chat_events(request: ChatRequest, response: ChatResponse) -> None:
    if response.errors:
        agent_event_store.append_event(
            type="analysis_failed",
            title="分析任务失败",
            summary=response.errors[-1],
            status="error",
            session_id=request.session_id,
            dataset_id=request.dataset_id,
            metadata={"message": request.message, "result_type": response.result.type},
            trace_steps=response.trace_steps,
        )
        return

    if response.result.type == "markdown":
        agent_event_store.append_event(
            type="report_generated",
            title="分析报告已生成",
            summary=response.result.summary or "已生成 Markdown 报告。",
            status="warning" if response.warnings else "success",
            session_id=request.session_id,
            dataset_id=request.dataset_id,
            metadata={"message": request.message, "markdown_length": len(response.answer)},
            trace_steps=response.trace_steps,
        )
        return

    agent_event_store.append_event(
        type="analysis_completed",
        title="分析任务完成",
        summary=response.result.summary or response.answer,
        status="warning" if response.warnings else "success",
        session_id=request.session_id,
        dataset_id=request.dataset_id,
        metadata={"message": request.message, "result_type": response.result.type},
        trace_steps=response.trace_steps,
    )

    chart_step = next((step for step in response.trace_steps if step.step == "build_chart_tool"), None)
    if response.charts:
        agent_event_store.append_event(
            type="chart_generated",
            title="图表已生成",
            summary=f"生成 {len(response.charts)} 个可视化图表。",
            status="success",
            session_id=request.session_id,
            dataset_id=request.dataset_id,
            metadata={"charts": [chart.model_dump() for chart in response.charts]},
            trace_steps=response.trace_steps,
        )
    elif chart_step and chart_step.status == "warning":
        agent_event_store.append_event(
            type="chart_fallback",
            title="图表生成已降级",
            summary="图表条件不足，已降级为表格结果。",
            status="warning",
            session_id=request.session_id,
            dataset_id=request.dataset_id,
            metadata={"warnings": response.warnings},
            trace_steps=response.trace_steps,
        )
