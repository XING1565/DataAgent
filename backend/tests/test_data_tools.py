from pathlib import Path

import pandas as pd

from app.schemas.chat import AnalysisResult
from app.schemas.dataset import ColumnSchema
from app.services.chart_service import ChartService
from app.services.dataset_store import DatasetStore
from app.services.pandasai_service import PandasAIServiceError
from app.services.report_service import ReportService
from app.services.session_store import SessionStore
from app.tools.data_tools import DataAgentTools


class RecordingAnalysisService:
    def analyze(
        self,
        dataframe: pd.DataFrame,
        question: str,
        schema: list[ColumnSchema],
    ) -> AnalysisResult:
        return AnalysisResult(type="text", value="ok", summary=f"answered: {question}")


class FailingAnalysisService:
    def analyze(
        self,
        dataframe: pd.DataFrame,
        question: str,
        schema: list[ColumnSchema],
    ) -> AnalysisResult:
        raise PandasAIServiceError("analysis failed")


def test_analyze_table_returns_tool_execution_result(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("product,sales\nA,10\n", encoding="utf-8")
    dataset = store.create_from_path(csv_path)
    tools = DataAgentTools(dataset_store=store, pandasai_service=RecordingAnalysisService())

    result = tools.analyze_table(dataset.dataset_id, "top product", session_id="sess_tools")

    assert result.tool_name == "analyze_table"
    assert result.status == "success"
    assert result.duration_ms >= 0
    assert result.payload["analysis_result"].summary == "answered: top product"
    assert result.fallback_used is False


def test_analyze_table_returns_error_result_when_analysis_fails(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("product,sales\nA,10\n", encoding="utf-8")
    dataset = store.create_from_path(csv_path)
    tools = DataAgentTools(dataset_store=store, pandasai_service=FailingAnalysisService())

    result = tools.analyze_table(dataset.dataset_id, "top product")

    assert result.status == "error"
    assert result.error_message == "analysis failed"


def test_query_dataset_returns_dataframe_result(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("product,sales\nA,10\nB,20\n", encoding="utf-8")
    dataset = store.create_from_path(csv_path)
    tools = DataAgentTools(dataset_store=store)

    result = tools.query_dataset(dataset.dataset_id, "SELECT product, sales FROM main_table ORDER BY sales DESC")

    assert result.tool_name == "query_dataset"
    assert result.status == "success"
    assert result.payload["rows"] == 2
    assert result.payload["columns"] == 2
    assert result.payload["analysis_result"].type == "dataframe"
    assert result.payload["analysis_result"].value[0] == {"product": "B", "sales": 20}


def test_query_dataset_returns_error_for_invalid_sql(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("product,sales\nA,10\n", encoding="utf-8")
    dataset = store.create_from_path(csv_path)
    tools = DataAgentTools(dataset_store=store)

    result = tools.query_dataset(dataset.dataset_id, "SELECT missing_column FROM main_table")

    assert result.status == "error"
    assert result.error_message


def test_query_dataset_returns_error_for_missing_dataset(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    tools = DataAgentTools(dataset_store=store)

    result = tools.query_dataset("ds_missing", "SELECT * FROM main_table")

    assert result.status == "error"
    assert result.error_message


def test_build_chart_returns_artifact(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("month,sales\n2026-01,100\n2026-02,150\n", encoding="utf-8")
    dataset = store.create_from_path(csv_path)
    tools = DataAgentTools(
        dataset_store=store,
        chart_service=ChartService(base_dir=tmp_path / "data"),
    )

    result = tools.build_chart(dataset.dataset_id, "plot monthly sales trend")

    assert result.status in {"success", "warning"}
    assert result.payload["charts"][0].url.startswith("/artifacts/chart_")
    assert result.payload["charts"][0].format == "html"


def test_build_chart_falls_back_to_table_when_columns_are_missing(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("product,region\nA,east\n", encoding="utf-8")
    dataset = store.create_from_path(csv_path)
    tools = DataAgentTools(
        dataset_store=store,
        chart_service=ChartService(base_dir=tmp_path / "data"),
    )

    result = tools.build_chart(dataset.dataset_id, "plot monthly sales trend")

    assert result.status == "warning"
    assert result.payload["analysis_result"].type == "dataframe"
    assert result.payload["charts"] == []
    assert result.fallback_used is True


def test_build_chart_selects_bar_pie_and_scatter(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("product,sales,profit\nA,100,20\nB,200,50\n", encoding="utf-8")
    dataset = store.create_from_path(csv_path)
    tools = DataAgentTools(
        dataset_store=store,
        chart_service=ChartService(base_dir=tmp_path / "data"),
    )

    bar_result = tools.build_chart(dataset.dataset_id, "compare product sales ranking")
    pie_result = tools.build_chart(dataset.dataset_id, "show sales share by product")
    scatter_result = tools.build_chart(dataset.dataset_id, "show sales profit correlation")

    assert bar_result.payload["charts"][0].type == "bar"
    assert pie_result.payload["charts"][0].type == "pie"
    assert scatter_result.payload["charts"][0].type == "scatter"


def test_export_report_returns_markdown(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")
    session_store = SessionStore(base_dir=tmp_path / "data")
    report_service = ReportService(session_store=session_store, dataset_store=store, base_dir=tmp_path / "data")
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("product,sales\nA,10\n", encoding="utf-8")
    dataset = store.create_from_path(csv_path)
    tools = DataAgentTools(dataset_store=store, report_service=report_service)

    result = tools.export_report("sess_tools", dataset.dataset_id, analysis_summary="A leads")

    assert result.status == "success"
    assert result.payload["report_markdown"].startswith("#")
    assert "A leads" in result.payload["report_markdown"]


def test_export_report_falls_back_to_minimal_markdown(tmp_path: Path) -> None:
    class BrokenReportService:
        def generate_markdown(self, session_id: str, dataset_id: str | None = None) -> str:
            raise RuntimeError("report failed")

    tools = DataAgentTools(report_service=BrokenReportService())

    result = tools.export_report("sess_tools", "ds_missing", analysis_summary="summary")

    assert result.status == "warning"
    assert result.fallback_used is True
    assert result.error_message == "report failed"
    assert "报告导出失败" in result.payload["report_markdown"]
