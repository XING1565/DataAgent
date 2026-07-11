from pathlib import Path
import json

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import chat
from app.graph.analysis_graph import AnalysisGraph
from app.main import app
from app.services.agent_event_store import AgentEventStore
from app.services.dataset_store import DatasetStore
from app.services.jobs_store import JobsStore
from app.services.pandasai_service import PandasAIService
from app.services.session_store import SessionStore


client = TestClient(app)


@pytest.fixture(autouse=True)
def isolate_chat_dependencies(tmp_path: Path) -> None:
    original_graph = chat.analysis_graph
    original_event_store = chat.agent_event_store
    original_jobs_store = chat.jobs_store
    session_store = SessionStore(base_dir=tmp_path / "data")
    chat.analysis_graph = AnalysisGraph(
        dataset_store=DatasetStore(base_dir=tmp_path / "data"),
        pandasai_service=PandasAIService(),
        session_store=session_store,
    )
    chat.agent_event_store = AgentEventStore(base_dir=tmp_path / "data")
    chat.jobs_store = JobsStore(base_dir=tmp_path / "data")
    try:
        yield
    finally:
        chat.analysis_graph = original_graph
        chat.agent_event_store = original_event_store
        chat.jobs_store = original_jobs_store


def test_chat_missing_dataset_returns_readable_error() -> None:
    response = client.post(
        "/api/v1/chat",
        json={
            "session_id": "sess_demo",
            "dataset_id": "ds_missing",
            "message": "top product by sales",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["result"]["type"] == "error"
    assert body["errors"]
    assert body["charts"] == []
    assert body["warnings"] == []
    assert body["trace_steps"][0]["step"] == "load_dataset"
    assert body["trace_steps"][0]["status"] == "error"
    events = chat.agent_event_store.get_events(session_id="sess_demo")
    assert events[0].type == "analysis_failed"
    jobs = chat.jobs_store.list_jobs(session_id="sess_demo")
    assert jobs[0].type == "analysis"
    assert jobs[0].status == "failed"


def test_chat_generate_report_enters_graph_and_returns_markdown() -> None:
    chat.analysis_graph.session_store.append_turn(
        session_id="sess_demo",
        dataset_id="ds_1",
        message="plot monthly sales trend",
        resolved_message="plot monthly sales trend",
        result_summary="Generated a monthly sales trend chart.",
        charts=[],
        warnings=[],
        errors=[],
    )

    response = client.post(
        "/api/v1/chat",
        json={
            "session_id": "sess_demo",
            "dataset_id": "ds_1",
            "message": "生成分析报告",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["result"]["type"] == "markdown"
    assert body["answer"].startswith("#")
    assert any(step["step"] == "load_dataset" and step["status"] == "warning" for step in body["trace_steps"])
    assert any(step["step"] == "analyze_table_tool" and step["status"] == "skipped" for step in body["trace_steps"])
    export_step = next(step for step in body["trace_steps"] if step["step"] == "export_report_tool")
    assert export_step["status"] == "success"
    assert export_step["tool_name"] == "export_report"
    events = chat.agent_event_store.get_events(session_id="sess_demo")
    assert events[0].type == "report_generated"


def _parse_sse_events(body: str) -> list[dict]:
    events = []
    for block in body.strip().split("\n\n"):
        if not block.strip():
            continue
        data_lines = [line.removeprefix("data: ").strip() for line in block.splitlines() if line.startswith("data:")]
        if data_lines:
            events.append(json.loads("\n".join(data_lines)))
    return events


def test_chat_stream_returns_trace_response_and_done() -> None:
    store = chat.analysis_graph.dataset_store
    csv_path = store.uploads_dir / "sales.csv"
    csv_path.write_text("product,sales\nA,300\nB,200\n", encoding="utf-8")
    dataset = store.create_from_path(csv_path)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "session_id": "sess_stream",
            "dataset_id": dataset.dataset_id,
            "message": "top product by sales",
        },
        headers={"Accept": "text/event-stream"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse_events(response.text)
    event_types = [event["type"] for event in events]
    assert "step_started" in event_types
    assert "step_finished" in event_types
    assert "response" in event_types
    assert event_types[-1] == "done"
    response_event = next(event for event in events if event["type"] == "response")
    assert response_event["response"]["dataset_id"] == dataset.dataset_id
    assert response_event["response"]["trace_steps"]
    assert chat.agent_event_store.get_events(session_id="sess_stream")
    jobs = chat.jobs_store.list_jobs(session_id="sess_stream")
    assert jobs[0].status == "succeeded"
    assert any(event.type == "step_finished" for event in chat.jobs_store.list_events(jobs[0].id))


def test_chat_stream_emits_chart_event_for_chart_request() -> None:
    store = chat.analysis_graph.dataset_store
    csv_path = store.uploads_dir / "sales.csv"
    csv_path.write_text("month,sales\n2026-01,100\n2026-02,180\n", encoding="utf-8")
    dataset = store.create_from_path(csv_path)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "session_id": "sess_stream_chart",
            "dataset_id": dataset.dataset_id,
            "message": "plot monthly sales trend",
        },
        headers={"Accept": "text/event-stream"},
    )

    events = _parse_sse_events(response.text)
    chart_events = [event for event in events if event["type"] == "chart"]
    assert chart_events
    assert chart_events[0]["chart"]["url"].startswith("/artifacts/chart_")
    jobs = chat.jobs_store.list_jobs(session_id="sess_stream_chart")
    assert jobs[0].result_json["charts"]


def test_chat_stream_missing_dataset_finishes_with_error_response() -> None:
    response = client.post(
        "/api/v1/chat/stream",
        json={
            "session_id": "sess_stream_missing",
            "dataset_id": "ds_missing",
            "message": "top product by sales",
        },
        headers={"Accept": "text/event-stream"},
    )

    events = _parse_sse_events(response.text)
    response_event = next(event for event in events if event["type"] == "response")
    assert response_event["response"]["result"]["type"] == "error"
    assert response_event["response"]["errors"]
    assert events[-1]["type"] == "done"
