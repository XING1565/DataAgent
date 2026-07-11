from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import reports
from app.main import app
from app.services.agent_event_store import AgentEventStore
from app.services.dataset_store import DatasetStore
from app.services.jobs_store import JobsStore
from app.services.report_service import ReportService
from app.services.session_store import SessionStore


client = TestClient(app)


@pytest.fixture(autouse=True)
def isolate_report_service(tmp_path: Path) -> None:
    original_service = reports.report_service
    original_event_store = reports.agent_event_store
    original_jobs_store = reports.jobs_store
    base_dir = tmp_path / "data"
    session_store = SessionStore(base_dir=base_dir)
    dataset_store = DatasetStore(base_dir=base_dir)
    reports.report_service = ReportService(session_store=session_store, dataset_store=dataset_store)
    reports.agent_event_store = AgentEventStore(base_dir=base_dir)
    reports.jobs_store = JobsStore(base_dir=base_dir)
    try:
        yield dataset_store
    finally:
        reports.report_service = original_service
        reports.agent_event_store = original_event_store
        reports.jobs_store = original_jobs_store


def test_create_report_returns_metadata_markdown(tmp_path: Path) -> None:
    dataset_store = reports.report_service.dataset_store
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("日期,销售额\n2026-01,15000\n2026-02,17200\n", encoding="utf-8")
    dataset = dataset_store.create_from_path(csv_path)
    reports.agent_event_store.append_event(
        type="alert_generated",
        title="销售额波动预警",
        summary="2026-02 销售额出现异常波动。",
        status="warning",
        session_id="sess_demo",
        dataset_id=dataset.dataset_id,
        metadata={
            "root_cause": "销售额时间序列出现明显波动。",
            "evidence": ["2026-02 销售额 17200"],
            "recommendation": "按渠道和产品拆解销售额变化。",
            "severity": "medium",
            "action_status": "open",
        },
    )

    response = client.post("/api/v1/reports", json={"session_id": "sess_demo", "dataset_id": dataset.dataset_id})

    body = response.json()
    assert response.status_code == 200
    assert body["session_id"] == "sess_demo"
    assert "# 数据分析报告" in body["report_markdown"]
    assert "字段与数据质量附录" in body["report_markdown"]
    assert "分析轮次" not in body["report_markdown"]
    events = reports.agent_event_store.get_events(session_id="sess_demo")
    report_events = [event for event in events if event.type == "report_generated"]
    alert_events = [event for event in events if event.type == "alert_generated"]
    assert len(report_events) == 1
    assert len(alert_events) == 1
    assert report_events[0].dataset_id == dataset.dataset_id
    assert report_events[0].metadata["markdown_length"] == len(body["report_markdown"])
    jobs = reports.jobs_store.list_jobs(session_id="sess_demo")
    assert jobs[0].type == "report"
    assert jobs[0].status == "succeeded"
    assert alert_events[0].metadata["root_cause"] == "销售额时间序列出现明显波动。"
