from pathlib import Path

from app.schemas.chat import AgentTraceStep
from app.services.agent_event_store import AgentEventStore


def test_agent_event_store_writes_and_reads_events(tmp_path: Path) -> None:
    store = AgentEventStore(base_dir=tmp_path / "data")

    event = store.append_event(
        type="analysis_completed",
        title="分析完成",
        summary="已完成销售分析。",
        session_id="sess_demo",
        dataset_id="ds_1",
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

    events = store.get_events(session_id="sess_demo")
    assert events == [event]
    assert events[0].trace_steps[0].step == "finalize"


def test_agent_event_store_reads_all_sessions_sorted(tmp_path: Path) -> None:
    store = AgentEventStore(base_dir=tmp_path / "data")

    first = store.append_event(type="dataset_uploaded", title="上传", summary="A", session_id="global")
    second = store.append_event(type="report_generated", title="报告", summary="B", session_id="sess_demo")

    events = store.get_events()
    assert {event.event_id for event in events} == {first.event_id, second.event_id}
    assert len(events) == 2


def test_agent_event_store_bad_json_returns_empty_list(tmp_path: Path) -> None:
    store = AgentEventStore(base_dir=tmp_path / "data")
    event_path = store.events_dir / "sess_bad.json"
    event_path.write_text("{bad json", encoding="utf-8")

    assert store.get_events(session_id="sess_bad") == []


def test_agent_event_store_status_uses_latest_events(tmp_path: Path) -> None:
    store = AgentEventStore(base_dir=tmp_path / "data")
    store.append_event(type="chart_fallback", title="图表降级", summary="已降级", status="warning", session_id="sess_demo")

    status = store.get_status(session_id="sess_demo")

    assert status.status == "warning"
    assert status.total_events == 1
    assert status.warning_count == 1
    assert status.last_event is not None
    assert status.last_event.type == "chart_fallback"
