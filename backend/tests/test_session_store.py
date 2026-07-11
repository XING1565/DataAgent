from pathlib import Path

from app.schemas.chat import ChartArtifact
from app.services.session_store import SessionStore


def test_session_store_saves_and_reads_history(tmp_path: Path) -> None:
    store = SessionStore(base_dir=tmp_path / "data")
    chart = ChartArtifact(chart_id="chart_1", type="line", title="趋势", url="/artifacts/chart_1.png")

    store.append_turn(
        session_id="sess_demo",
        dataset_id="ds_1",
        message="按月份画销售趋势",
        resolved_message="按月份画销售趋势",
        result_summary="已生成按月份销售趋势图。",
        charts=[chart],
        warnings=[],
        errors=[],
    )

    history = store.get_history("sess_demo")
    assert len(history) == 1
    assert history[0]["topic"] == "销售趋势"
    assert history[0]["charts"][0]["chart_id"] == "chart_1"


def test_session_store_resolves_follow_up_context(tmp_path: Path) -> None:
    store = SessionStore(base_dir=tmp_path / "data")
    store.append_turn(
        session_id="sess_demo",
        dataset_id="ds_1",
        message="按月份画销售趋势",
        resolved_message="按月份画销售趋势",
        result_summary="已生成按月份销售趋势图。",
        charts=[],
        warnings=[],
        errors=[],
    )

    resolved = store.resolve_message("sess_demo", "那哪个地区下降最多")

    assert resolved == "在上一轮销售趋势分析中，按地区比较销售额下降幅度，那哪个地区下降最多"
