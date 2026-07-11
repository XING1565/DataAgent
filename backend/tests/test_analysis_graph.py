from pathlib import Path

import pandas as pd

from app.graph.analysis_graph import AnalysisGraph
from app.schemas.chat import AnalysisResult
from app.schemas.dataset import ColumnSchema
from app.services.chart_service import ChartService
from app.services.dataset_store import DatasetStore
from app.services.pandasai_service import PandasAIService, PandasAIServiceError
from app.services.session_store import SessionStore


class RecordingPandasAIService:
    def __init__(self) -> None:
        self.questions: list[str] = []

    def analyze(
        self,
        dataframe: pd.DataFrame,
        question: str,
        schema: list[ColumnSchema],
    ) -> AnalysisResult:
        self.questions.append(question)
        return AnalysisResult(
            type="dataframe",
            value=[
                {"产品": "A", "销售额": 300},
                {"产品": "B", "销售额": 200},
                {"产品": "C", "销售额": 100},
            ],
            summary="销售额最高的三个产品是 A、B、C。",
        )


class FailingPandasAIService:
    def analyze(
        self,
        dataframe: pd.DataFrame,
        question: str,
        schema: list[ColumnSchema],
    ) -> AnalysisResult:
        raise PandasAIServiceError("PandasAI 分析失败，请检查 LLM 配置或稍后重试。")


def test_analysis_graph_returns_standard_result(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("产品,销售额\nA,300\nB,200\nC,100\n", encoding="utf-8")
    dataset = store.create_from_path(csv_path)
    graph = AnalysisGraph(dataset_store=store, pandasai_service=RecordingPandasAIService())

    response = graph.run(
        session_id="sess_demo",
        dataset_id=dataset.dataset_id,
        message="销售额最高的三个产品是什么",
    )

    assert response.session_id == "sess_demo"
    assert response.dataset_id == dataset.dataset_id
    assert response.result.type == "dataframe"
    assert response.answer == "销售额最高的三个产品是 A、B、C。"
    assert response.charts == []
    assert response.warnings == []
    assert response.errors == []
    assert [step.step for step in response.trace_steps] == [
        "load_dataset",
        "resolve_context",
        "detect_command",
        "analyze_table_tool",
        "build_chart_tool",
        "export_report_tool",
        "save_session",
        "finalize",
    ]
    assert all(step.duration_ms >= 0 for step in response.trace_steps)
    assert response.trace_steps[0].status == "success"


def test_analysis_graph_returns_readable_error_when_pandasai_fails(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("产品,销售额\nA,300\n", encoding="utf-8")
    dataset = store.create_from_path(csv_path)
    graph = AnalysisGraph(dataset_store=store, pandasai_service=FailingPandasAIService())

    response = graph.run(
        session_id="sess_demo",
        dataset_id=dataset.dataset_id,
        message="销售额最高的三个产品是什么",
    )

    assert response.result.type == "error"
    assert response.answer == "PandasAI 分析失败，请检查 LLM 配置或稍后重试。"
    assert response.errors == ["PandasAI 分析失败，请检查 LLM 配置或稍后重试。"]
    assert response.trace_steps[-1].step == "finalize"
    assert response.trace_steps[-1].status == "error"
    assert any(step.step == "analyze_table_tool" and step.status == "error" for step in response.trace_steps)


def test_sql_command_query_branch_returns_dataframe(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("product,sales\nA,300\nB,200\nC,100\n", encoding="utf-8")
    dataset = store.create_from_path(csv_path)
    pandasai_service = RecordingPandasAIService()
    graph = AnalysisGraph(dataset_store=store, pandasai_service=pandasai_service)

    response = graph.run(
        session_id="sess_sql",
        dataset_id=dataset.dataset_id,
        message="/sql SELECT COUNT(*) AS cnt FROM main_table",
    )

    assert response.result.type == "dataframe"
    assert response.result.value == [{"cnt": 3}]
    assert response.answer == "SQL query returned 1 rows and 1 columns."
    assert response.errors == []
    assert pandasai_service.questions == []
    assert [step.step for step in response.trace_steps] == [
        "load_dataset",
        "resolve_context",
        "detect_command",
        "plan_query",
        "execute_query_tool",
        "analyze_query_result",
        "build_chart_tool",
        "export_report_tool",
        "save_session",
        "finalize",
    ]
    plan_step = next(step for step in response.trace_steps if step.step == "plan_query")
    execute_step = next(step for step in response.trace_steps if step.step == "execute_query_tool")
    assert plan_step.details["sql"] == "SELECT COUNT(*) AS cnt FROM main_table"
    assert execute_step.details == {
        "sql": "SELECT COUNT(*) AS cnt FROM main_table",
        "rows": 1,
        "columns": 1,
    }
    assert execute_step.tool_name == "query_dataset"


def test_direct_select_query_uses_sql_branch(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("product,sales\nA,300\nB,200\nC,100\n", encoding="utf-8")
    dataset = store.create_from_path(csv_path)
    pandasai_service = RecordingPandasAIService()
    graph = AnalysisGraph(dataset_store=store, pandasai_service=pandasai_service)

    response = graph.run(
        session_id="sess_sql",
        dataset_id=dataset.dataset_id,
        message="SELECT product FROM main_table ORDER BY sales DESC LIMIT 2",
    )

    assert response.result.type == "dataframe"
    assert response.result.value == [{"product": "A"}, {"product": "B"}]
    assert pandasai_service.questions == []
    assert any(step.step == "execute_query_tool" and step.status == "success" for step in response.trace_steps)


def test_invalid_sql_query_returns_error_result(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("product,sales\nA,300\n", encoding="utf-8")
    dataset = store.create_from_path(csv_path)
    graph = AnalysisGraph(dataset_store=store, pandasai_service=RecordingPandasAIService())

    response = graph.run(
        session_id="sess_sql",
        dataset_id=dataset.dataset_id,
        message="/sql SELECT missing_column FROM main_table",
    )

    assert response.result.type == "error"
    assert response.errors
    assert "SQL query failed" in response.answer
    execute_step = next(step for step in response.trace_steps if step.step == "execute_query_tool")
    assert execute_step.status == "error"
    assert execute_step.error_message
    assert response.trace_steps[-1].step == "finalize"
    assert response.trace_steps[-1].status == "error"


def test_natural_language_request_stays_on_pandasai_branch(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("product,sales\nA,300\nB,200\n", encoding="utf-8")
    dataset = store.create_from_path(csv_path)
    pandasai_service = RecordingPandasAIService()
    graph = AnalysisGraph(dataset_store=store, pandasai_service=pandasai_service)

    response = graph.run(
        session_id="sess_demo",
        dataset_id=dataset.dataset_id,
        message="Which product has the highest sales?",
    )

    assert pandasai_service.questions == ["Which product has the highest sales?"]
    assert "analyze_table_tool" in [step.step for step in response.trace_steps]
    assert "execute_query_tool" not in [step.step for step in response.trace_steps]


def test_data_command_returns_dataset_overview(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("product,sales\nA,300\nB,\nB,\n", encoding="utf-8")
    dataset = store.create_from_path(csv_path)
    graph = AnalysisGraph(dataset_store=store, pandasai_service=RecordingPandasAIService())

    response = graph.run("sess_cmd", dataset.dataset_id, "/data")

    assert response.result.type == "markdown"
    assert "数据集概况" in str(response.result.value)
    assert response.answer == "数据集包含 3 行、2 列。"
    assert any(step.step == "detect_command" and step.status == "success" for step in response.trace_steps)
    assert any(step.step == "dataset_overview_tool" and step.status == "success" for step in response.trace_steps)


def test_chart_command_skips_pandasai_and_builds_chart(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("product,sales\nA,300\nB,200\n", encoding="utf-8")
    dataset = store.create_from_path(csv_path)
    pandasai_service = RecordingPandasAIService()
    graph = AnalysisGraph(
        dataset_store=store,
        pandasai_service=pandasai_service,
        chart_service=ChartService(base_dir=tmp_path / "data"),
        session_store=SessionStore(base_dir=tmp_path / "data"),
    )

    response = graph.run("sess_cmd", dataset.dataset_id, "/chart compare product sales")

    assert response.result.type == "chart"
    assert response.charts
    assert pandasai_service.questions == []
    assert "analyze_table_tool" not in [step.step for step in response.trace_steps]
    assert any(step.step == "build_chart_tool" for step in response.trace_steps)


def test_report_command_triggers_report_tool(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("product,sales\nA,300\n", encoding="utf-8")
    dataset = store.create_from_path(csv_path)
    graph = AnalysisGraph(
        dataset_store=store,
        pandasai_service=RecordingPandasAIService(),
        session_store=SessionStore(base_dir=tmp_path / "data"),
    )

    response = graph.run("sess_cmd_report", dataset.dataset_id, "/report")

    assert response.result.type == "markdown"
    assert response.answer.startswith("#")
    assert any(step.step == "export_report_tool" and step.status == "success" for step in response.trace_steps)


def test_clean_command_returns_quality_advice(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("product,sales\nA,300\nB,\nB,\n", encoding="utf-8")
    dataset = store.create_from_path(csv_path)
    graph = AnalysisGraph(dataset_store=store, pandasai_service=RecordingPandasAIService())

    response = graph.run("sess_cmd_clean", dataset.dataset_id, "/clean")

    assert response.result.type == "markdown"
    assert "数据质量与清洗建议" in str(response.result.value)
    assert any(step.step == "data_cleaning_tool" and step.status == "success" for step in response.trace_steps)


def test_unknown_command_returns_error_with_available_commands(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("product,sales\nA,300\n", encoding="utf-8")
    dataset = store.create_from_path(csv_path)
    graph = AnalysisGraph(dataset_store=store, pandasai_service=RecordingPandasAIService())

    response = graph.run("sess_cmd_unknown", dataset.dataset_id, "/unknown")

    assert response.result.type == "error"
    assert "/data" in response.answer
    assert any(step.step == "detect_command" and step.status == "error" for step in response.trace_steps)


def test_chart_request_returns_chart_artifact(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text(
        "月份,销售额,地区\n2026-01,100,华东\n2026-02,180,华东\n2026-03,150,华东\n",
        encoding="utf-8",
    )
    dataset = store.create_from_path(csv_path)
    graph = AnalysisGraph(
        dataset_store=store,
        pandasai_service=RecordingPandasAIService(),
        chart_service=ChartService(base_dir=tmp_path / "data"),
        session_store=SessionStore(base_dir=tmp_path / "data"),
    )

    response = graph.run(
        session_id="sess_chart",
        dataset_id=dataset.dataset_id,
        message="按月份画销售趋势",
    )

    assert response.result.type == "chart"
    assert "line" in response.result.summary
    assert response.charts[0].type == "line"
    assert response.charts[0].url.startswith("/artifacts/chart_")
    assert response.charts[0].format == "html"
    assert (tmp_path / "data" / "artifacts" / f"{response.charts[0].chart_id}.html").exists()
    visualize_step = next(step for step in response.trace_steps if step.step == "build_chart_tool")
    assert visualize_step.status in {"success", "warning"}
    assert visualize_step.action == "call build_chart tool"
    assert visualize_step.details["charts_created"] == 1
    assert visualize_step.tool_name == "build_chart"


def test_chart_request_falls_back_to_table_when_columns_missing(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("产品,地区\nA,华东\nB,华北\n", encoding="utf-8")
    dataset = store.create_from_path(csv_path)
    graph = AnalysisGraph(
        dataset_store=store,
        pandasai_service=RecordingPandasAIService(),
        chart_service=ChartService(base_dir=tmp_path / "data"),
        session_store=SessionStore(base_dir=tmp_path / "data"),
    )

    response = graph.run(
        session_id="sess_chart",
        dataset_id=dataset.dataset_id,
        message="按月份画销售趋势",
    )

    assert response.result.type == "dataframe"
    assert response.charts == []
    assert response.warnings
    visualize_step = next(step for step in response.trace_steps if step.step == "build_chart_tool")
    assert visualize_step.status == "warning"
    assert visualize_step.details["charts_created"] == 0
    assert visualize_step.fallback_used is True


def test_follow_up_region_decline_uses_context_without_repeating_chart(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text(
        "月份,销售额,地区\n2026-01,100,华东\n2026-02,80,华东\n2026-01,200,华北\n2026-02,190,华北\n",
        encoding="utf-8",
    )
    dataset = store.create_from_path(csv_path)
    graph = AnalysisGraph(
        dataset_store=store,
        pandasai_service=PandasAIService(),
        chart_service=ChartService(base_dir=tmp_path / "data"),
        session_store=SessionStore(base_dir=tmp_path / "data"),
    )

    graph.run("sess_follow", dataset.dataset_id, "按月份画销售趋势")
    response = graph.run("sess_follow", dataset.dataset_id, "哪个地区下降最多")

    assert response.result.type == "dataframe"
    assert response.charts == []
    assert "下降最多的地区是华东" in response.answer
    visualize_step = next(step for step in response.trace_steps if step.step == "build_chart_tool")
    assert visualize_step.status == "skipped"
