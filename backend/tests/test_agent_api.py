from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import agent
from app.main import app
from app.schemas.chat import AgentTraceStep
from app.services.agent_event_store import AgentEventStore


client = TestClient(app)


@pytest.fixture(autouse=True)
def isolate_agent_event_store(tmp_path: Path) -> None:
    original_store = agent.agent_event_store
    agent.agent_event_store = AgentEventStore(base_dir=tmp_path / "data")
    try:
        yield
    finally:
        agent.agent_event_store = original_store


def test_agent_status_returns_idle_when_no_events() -> None:
    response = client.get("/api/v1/agent/status")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "idle"
    assert body["total_events"] == 0


def test_agent_events_returns_recorded_events() -> None:
    agent.agent_event_store.append_event(
        type="dataset_uploaded",
        title="数据集上传完成",
        summary="sales.csv",
        dataset_id="ds_1",
    )

    response = client.get("/api/v1/agent/events")

    body = response.json()
    assert response.status_code == 200
    assert body["events"][0]["type"] == "dataset_uploaded"
    assert body["events"][0]["dataset_id"] == "ds_1"


def test_agent_session_trace_returns_latest_trace() -> None:
    agent.agent_event_store.append_event(
        type="analysis_completed",
        title="分析完成",
        summary="ok",
        session_id="sess_demo",
        trace_steps=[
            AgentTraceStep(
                step="finalize",
                status="success",
                duration_ms=1,
                observation="done",
                action="return response",
            )
        ],
    )

    response = client.get("/api/v1/agent/sessions/sess_demo/trace")

    body = response.json()
    assert response.status_code == 200
    assert body["session_id"] == "sess_demo"
    assert body["trace_steps"][0]["step"] == "finalize"
