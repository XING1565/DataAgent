from pathlib import Path

import pandas as pd

from app.services.chart_service import ChartService


def test_select_chart_recognizes_core_intents(tmp_path: Path) -> None:
    service = ChartService(base_dir=tmp_path / "data")

    assert service.select_chart("查看销售趋势") == "line"
    assert service.select_chart("按产品排名对比") == "bar"
    assert service.select_chart("渠道占比构成") == "pie"
    assert service.select_chart("价格和销量相关关系") == "scatter"
    assert service.select_chart("地区月份热力矩阵") == "heatmap"


def test_infer_field_mapping_for_common_chart_types(tmp_path: Path) -> None:
    service = ChartService(base_dir=tmp_path / "data")
    dataframe = pd.DataFrame(
        {
            "month": ["2026-01", "2026-02"],
            "region": ["east", "west"],
            "sales": [100, 200],
            "profit": [20, 30],
        }
    )

    assert service.infer_field_mapping("line", dataframe) == {"x": "month", "y": "sales"}
    assert service.infer_field_mapping("bar", dataframe) == {"x": "month", "y": "sales"}
    assert service.infer_field_mapping("pie", dataframe) == {"label": "month", "value": "sales"}
    assert service.infer_field_mapping("scatter", dataframe) == {"x": "sales", "y": "profit"}
    assert service.infer_field_mapping("heatmap", dataframe) == {"x": "month", "y": "region", "value": "sales"}


def test_render_chart_generates_html_artifact(tmp_path: Path) -> None:
    service = ChartService(base_dir=tmp_path / "data")
    dataframe = pd.DataFrame({"product": ["A", "B"], "sales": [100, 200]})

    result, charts, warnings = service.render_chart("bar", dataframe, {"x": "product", "y": "sales"})

    assert result.type == "chart"
    assert charts[0].type == "bar"
    assert charts[0].format == "html"
    assert charts[0].url.endswith(".html")
    assert (tmp_path / "data" / "artifacts" / f"{charts[0].chart_id}.html").exists()
    assert isinstance(warnings, list)


def test_render_chart_falls_back_when_mapping_is_incomplete(tmp_path: Path) -> None:
    service = ChartService(base_dir=tmp_path / "data")
    dataframe = pd.DataFrame({"product": ["A", "B"]})

    result, charts, warnings = service.render_chart("bar", dataframe, {"x": "product"})

    assert result.type == "dataframe"
    assert charts == []
    assert warnings


def test_chart_service_generates_trend_chart_with_value_summary(tmp_path: Path) -> None:
    service = ChartService(base_dir=tmp_path / "data")
    dataframe = pd.DataFrame(
        {
            "月份": ["2026-01", "2026-02", "2026-02"],
            "销售额": [100, 180, 20],
        }
    )

    result, charts, warnings = service.build_trend_chart(dataframe, "按月份画销售趋势")

    assert result.type == "chart"
    assert result.value == [{"月份": "2026-01", "销售额": 100}, {"月份": "2026-02", "销售额": 200}]
    assert "2026-01: 100" in result.summary
    assert "2026-02: 200 (+100.0%)" in result.summary
    assert charts[0].url.startswith("/artifacts/chart_")
    assert (tmp_path / "data" / "artifacts" / f"{charts[0].chart_id}.png").exists()
    assert warnings == []


def test_chart_service_falls_back_when_columns_missing(tmp_path: Path) -> None:
    service = ChartService(base_dir=tmp_path / "data")
    dataframe = pd.DataFrame({"产品": ["A", "B"], "数量": [10, 20]})

    result, charts, warnings = service.build_trend_chart(dataframe, "按月份画销售趋势")

    assert result.type == "dataframe"
    assert "趋势表格" in result.summary
    assert charts == []
    assert warnings
