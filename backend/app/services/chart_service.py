from __future__ import annotations

from pathlib import Path
from secrets import token_hex
from typing import Any

import pandas as pd

from app.schemas.chat import AnalysisResult, ChartArtifact


CHART_REGISTRY = {
    "line": {"roles": ["x", "y"], "intent": ["趋势", "变化", "走势", "trend", "change", "line"]},
    "bar": {"roles": ["x", "y"], "intent": ["对比", "比较", "排名", "排行", "compare", "ranking", "rank", "bar"]},
    "pie": {"roles": ["label", "value"], "intent": ["占比", "构成", "比例", "份额", "share", "ratio", "pie"]},
    "scatter": {"roles": ["x", "y"], "intent": ["相关", "关系", "关联", "correlation", "relationship", "scatter"]},
    "heatmap": {"roles": ["x", "y", "value"], "intent": ["矩阵", "热力", "分布", "heatmap", "matrix"]},
}

TEXT_CHART_FALLBACK_WARNING = "图表生成失败，已降级为表格结果。"
TEXT_CHART_FALLBACK_SUMMARY = "图表生成失败，已降级返回趋势表格。"
TEXT_CHART_EMPTY_SUMMARY = "图表生成失败，未找到可展示的趋势数据。"
TEXT_CHART_TITLE = "按月份销售趋势"
TEXT_CHART_SUCCESS_SUMMARY = "已生成按月份销售趋势图。"
TEXT_GENERIC_CHART_SUCCESS_SUMMARY = "已生成交互式图表。"
TEXT_FIELD_MAPPING_WARNING = "未找到适合该图表类型的字段，已降级为表格结果。"
TEXT_PLOTLY_MISSING_WARNING = "Plotly 未安装，已使用轻量 HTML 图表兜底。"


class ChartService:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path(__file__).resolve().parents[3] / "data"
        self.artifacts_dir = self.base_dir / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def is_chart_request(self, message: str) -> bool:
        normalized = message.lower()
        keywords = [
            "图",
            "画",
            "趋势",
            "月份",
            "对比",
            "比较",
            "排名",
            "排行",
            "占比",
            "构成",
            "比例",
            "相关",
            "关系",
            "热力",
            "矩阵",
            "chart",
            "plot",
            "trend",
            "compare",
            "ranking",
            "rank",
            "share",
            "ratio",
            "correlation",
            "scatter",
            "heatmap",
            "bar",
            "pie",
        ]
        return any(keyword in normalized for keyword in keywords)

    def select_chart(
        self,
        message: str,
        schema: list[Any] | None = None,
        query_result: pd.DataFrame | None = None,
    ) -> str:
        normalized = message.lower()
        for chart_type, config in CHART_REGISTRY.items():
            if any(intent.lower() in normalized for intent in config["intent"]):
                return chart_type

        dataframe = query_result
        if dataframe is not None and not dataframe.empty:
            numeric_columns = self._numeric_columns(dataframe)
            categorical_columns = self._categorical_columns(dataframe)
            date_columns = self._date_columns(dataframe)
            if date_columns and numeric_columns:
                return "line"
            if len(numeric_columns) >= 2:
                return "scatter"
            if categorical_columns and numeric_columns:
                return "bar"
        return "bar"

    def infer_field_mapping(self, chart_type: str, dataframe: pd.DataFrame) -> dict[str, str]:
        numeric_columns = self._numeric_columns(dataframe)
        date_columns = self._date_columns(dataframe)
        categorical_columns = self._categorical_columns(dataframe)
        non_numeric_columns = date_columns + [column for column in categorical_columns if column not in date_columns]

        if chart_type == "line":
            return self._compact_mapping({"x": self._first(date_columns, categorical_columns, dataframe.columns), "y": self._first(numeric_columns)})
        if chart_type == "bar":
            return self._compact_mapping({"x": self._first(categorical_columns, date_columns, dataframe.columns), "y": self._first(numeric_columns)})
        if chart_type == "pie":
            return self._compact_mapping({"label": self._first(categorical_columns, date_columns, dataframe.columns), "value": self._first(numeric_columns)})
        if chart_type == "scatter":
            return self._compact_mapping({"x": self._first(numeric_columns), "y": self._first(numeric_columns[1:])})
        if chart_type == "heatmap":
            return self._compact_mapping(
                {
                    "x": self._first(non_numeric_columns, dataframe.columns),
                    "y": self._first(non_numeric_columns[1:], dataframe.columns[1:]),
                    "value": self._first(numeric_columns),
                }
            )
        return {}

    def build_chart(
        self,
        dataframe: pd.DataFrame,
        message: str,
        chart_type: str | None = None,
    ) -> tuple[AnalysisResult, list[ChartArtifact], list[str]]:
        selected_chart = chart_type if chart_type in CHART_REGISTRY else self.select_chart(message, query_result=dataframe)
        mapping = self.infer_field_mapping(selected_chart, dataframe)
        return self.render_chart(selected_chart, dataframe, mapping)

    def render_chart(
        self,
        chart_type: str,
        dataframe: pd.DataFrame,
        mapping: dict[str, str],
    ) -> tuple[AnalysisResult, list[ChartArtifact], list[str]]:
        warnings: list[str] = []
        required_roles = CHART_REGISTRY.get(chart_type, {}).get("roles", [])
        if not required_roles or any(role not in mapping for role in required_roles):
            warnings.append(TEXT_FIELD_MAPPING_WARNING)
            return (
                AnalysisResult(type="dataframe", value=self._fallback_table(dataframe, None, None), summary=TEXT_FIELD_MAPPING_WARNING),
                [],
                warnings,
            )

        try:
            chart_dataframe = self._prepare_chart_dataframe(chart_type, dataframe, mapping)
            if chart_dataframe.empty:
                warnings.append(TEXT_FIELD_MAPPING_WARNING)
                return (
                    AnalysisResult(type="dataframe", value=[], summary=TEXT_FIELD_MAPPING_WARNING),
                    [],
                    warnings,
                )

            chart_id = f"chart_{token_hex(4)}"
            filename = f"{chart_id}.html"
            path = self.artifacts_dir / filename
            plotly_warning = self._render_html_chart(chart_type, chart_dataframe, mapping, path)
            if plotly_warning:
                warnings.append(plotly_warning)
            chart = ChartArtifact(
                chart_id=chart_id,
                type=chart_type,
                title=self._chart_title(chart_type, mapping),
                url=f"/artifacts/{filename}",
                status="ok",
                format="html",
            )
            cleaned = chart_dataframe.astype(object).where(pd.notna(chart_dataframe), None)
            return (
                AnalysisResult(
                    type="chart",
                    value=cleaned.to_dict(orient="records"),
                    summary=f"{TEXT_GENERIC_CHART_SUCCESS_SUMMARY}类型：{chart_type}。",
                ),
                [chart],
                warnings,
            )
        except Exception:
            warnings.append(TEXT_CHART_FALLBACK_WARNING)
            return (
                AnalysisResult(type="dataframe", value=self._fallback_table(dataframe, None, None), summary=TEXT_CHART_FALLBACK_SUMMARY),
                [],
                warnings,
            )

    def build_trend_chart(
        self,
        dataframe: pd.DataFrame,
        message: str,
    ) -> tuple[AnalysisResult, list[ChartArtifact], list[str]]:
        month_column = self._find_column(dataframe, ["月份", "月", "日期", "时间", "date", "month", "time"])
        sales_column = self._find_column(dataframe, ["销售额", "销售", "金额", "收入", "sales", "amount", "revenue"])
        warnings: list[str] = []

        if not month_column or not sales_column:
            fallback = self._fallback_table(dataframe, month_column, sales_column)
            warnings.append(TEXT_CHART_FALLBACK_WARNING)
            return (
                AnalysisResult(type="dataframe", value=fallback, summary=TEXT_CHART_FALLBACK_SUMMARY),
                [],
                warnings,
            )

        trend = self._build_trend_table(dataframe, month_column, sales_column)
        if trend.empty:
            warnings.append(TEXT_CHART_FALLBACK_WARNING)
            return (
                AnalysisResult(type="dataframe", value=[], summary=TEXT_CHART_EMPTY_SUMMARY),
                [],
                warnings,
            )

        try:
            chart_id = f"chart_{token_hex(4)}"
            filename = f"{chart_id}.png"
            path = self.artifacts_dir / filename
            self._render_line_chart(trend, month_column, sales_column, path)
            chart = ChartArtifact(
                chart_id=chart_id,
                type="line",
                title=TEXT_CHART_TITLE,
                url=f"/artifacts/{filename}",
                status="ok",
                format="png",
            )
            return (
                AnalysisResult(type="chart", value=trend.to_dict(orient="records"), summary=self._build_trend_summary(trend, month_column, sales_column)),
                [chart],
                warnings,
            )
        except Exception:
            warnings.append(TEXT_CHART_FALLBACK_WARNING)
            return (
                AnalysisResult(type="dataframe", value=trend.to_dict(orient="records"), summary=TEXT_CHART_FALLBACK_SUMMARY),
                [],
                warnings,
            )

    def _render_line_chart(self, trend: pd.DataFrame, month_column: str, sales_column: str, path: Path) -> None:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.ticker import FuncFormatter

        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.plot(trend[month_column].astype(str), trend[sales_column], marker="o")
        ax.set_title("Monthly Sales Trend")
        ax.set_xlabel("Month")
        ax.set_ylabel("Sales")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))
        ax.grid(True, alpha=0.3)
        values = pd.to_numeric(trend[sales_column], errors="coerce")
        y_span = values.max() - values.min()
        y_offset = y_span * 0.04 if pd.notna(y_span) and y_span else max(values.max() * 0.03, 1)
        for index, (_, row) in enumerate(trend.iterrows()):
            value = float(row[sales_column])
            label = f"{value:,.0f}"
            if index > 0:
                previous = float(trend.iloc[index - 1][sales_column])
                if previous:
                    label = f"{label}\n({(value - previous) / previous:+.1%})"
            ax.annotate(label, (str(row[month_column]), value), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8)
        ax.set_ylim(bottom=max(0, values.min() - y_offset), top=values.max() + y_offset * 4)
        fig.autofmt_xdate(rotation=30)
        fig.tight_layout()
        fig.savefig(path, dpi=140)
        plt.close(fig)

    def _build_trend_table(self, dataframe: pd.DataFrame, month_column: str, sales_column: str) -> pd.DataFrame:
        working = dataframe[[month_column, sales_column]].copy()
        working[sales_column] = pd.to_numeric(working[sales_column], errors="coerce")
        parsed_date = pd.to_datetime(working[month_column], errors="coerce")
        if parsed_date.notna().any():
            working[month_column] = parsed_date.dt.to_period("M").astype(str)
        else:
            working[month_column] = working[month_column].astype(str)
        return (
            working.dropna(subset=[month_column, sales_column])
            .groupby(month_column, as_index=False)[sales_column]
            .sum()
            .sort_values(month_column)
        )

    def _build_trend_summary(self, trend: pd.DataFrame, month_column: str, sales_column: str) -> str:
        parts = []
        for index, (_, row) in enumerate(trend.iterrows()):
            value = float(row[sales_column])
            text = f"{row[month_column]}: {value:,.0f}"
            if index > 0:
                previous = float(trend.iloc[index - 1][sales_column])
                if previous:
                    text = f"{text} ({(value - previous) / previous:+.1%})"
            parts.append(text)
        return f"{TEXT_CHART_SUCCESS_SUMMARY}{'，'.join(parts)}。"

    def _prepare_chart_dataframe(self, chart_type: str, dataframe: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
        if chart_type in {"line", "bar"}:
            x_column = mapping["x"]
            y_column = mapping["y"]
            working = dataframe[[x_column, y_column]].copy()
            working[y_column] = pd.to_numeric(working[y_column], errors="coerce")
            if chart_type == "line":
                parsed_date = pd.to_datetime(working[x_column], errors="coerce")
                if parsed_date.notna().any():
                    working[x_column] = parsed_date.dt.to_period("M").astype(str)
            else:
                working[x_column] = working[x_column].astype(str)
            return (
                working.dropna(subset=[x_column, y_column])
                .groupby(x_column, as_index=False)[y_column]
                .sum()
                .sort_values(x_column)
                .head(50)
            )
        if chart_type == "pie":
            label_column = mapping["label"]
            value_column = mapping["value"]
            working = dataframe[[label_column, value_column]].copy()
            working[label_column] = working[label_column].astype(str)
            working[value_column] = pd.to_numeric(working[value_column], errors="coerce")
            return (
                working.dropna(subset=[label_column, value_column])
                .groupby(label_column, as_index=False)[value_column]
                .sum()
                .sort_values(value_column, ascending=False)
                .head(12)
            )
        if chart_type == "scatter":
            x_column = mapping["x"]
            y_column = mapping["y"]
            working = dataframe[[x_column, y_column]].copy()
            working[x_column] = pd.to_numeric(working[x_column], errors="coerce")
            working[y_column] = pd.to_numeric(working[y_column], errors="coerce")
            return working.dropna(subset=[x_column, y_column]).head(500)
        if chart_type == "heatmap":
            x_column = mapping["x"]
            y_column = mapping["y"]
            value_column = mapping["value"]
            working = dataframe[[x_column, y_column, value_column]].copy()
            working[x_column] = working[x_column].astype(str)
            working[y_column] = working[y_column].astype(str)
            working[value_column] = pd.to_numeric(working[value_column], errors="coerce")
            return working.dropna(subset=[x_column, y_column, value_column]).head(500)
        return dataframe.head(50)

    def _render_html_chart(self, chart_type: str, dataframe: pd.DataFrame, mapping: dict[str, str], path: Path) -> str | None:
        try:
            import plotly.express as px

            if chart_type == "line":
                figure = px.line(dataframe, x=mapping["x"], y=mapping["y"], markers=True, title=self._chart_title(chart_type, mapping))
            elif chart_type == "bar":
                figure = px.bar(dataframe, x=mapping["x"], y=mapping["y"], title=self._chart_title(chart_type, mapping))
            elif chart_type == "pie":
                figure = px.pie(dataframe, names=mapping["label"], values=mapping["value"], title=self._chart_title(chart_type, mapping))
            elif chart_type == "scatter":
                figure = px.scatter(dataframe, x=mapping["x"], y=mapping["y"], title=self._chart_title(chart_type, mapping))
            elif chart_type == "heatmap":
                pivot = dataframe.pivot_table(index=mapping["y"], columns=mapping["x"], values=mapping["value"], aggfunc="sum")
                figure = px.imshow(pivot, aspect="auto", title=self._chart_title(chart_type, mapping))
            else:
                raise ValueError(f"Unsupported chart type: {chart_type}")
            figure.write_html(path, include_plotlyjs="cdn", full_html=True)
            return None
        except ModuleNotFoundError:
            self._render_basic_html_chart(chart_type, dataframe, mapping, path)
            return TEXT_PLOTLY_MISSING_WARNING

    def _render_basic_html_chart(self, chart_type: str, dataframe: pd.DataFrame, mapping: dict[str, str], path: Path) -> None:
        records = dataframe.astype(object).where(pd.notna(dataframe), "").to_dict(orient="records")
        columns = list(dataframe.columns)
        rows = "\n".join(
            "<tr>" + "".join(f"<td>{self._html_escape(row.get(column, ''))}</td>" for column in columns) + "</tr>"
            for row in records[:100]
        )
        headers = "".join(f"<th>{self._html_escape(column)}</th>" for column in columns)
        title = self._html_escape(self._chart_title(chart_type, mapping))
        html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #172033; background: #ffffff; }}
    main {{ padding: 18px; }}
    h1 {{ margin: 0 0 12px; font-size: 18px; }}
    .meta {{ margin-bottom: 14px; color: #607086; font-size: 13px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #e5eaf0; padding: 8px; text-align: left; }}
    th {{ background: #f6f8fb; }}
  </style>
</head>
<body>
  <main>
    <h1>{title}</h1>
    <div class="meta">Plotly is not installed. Showing the chart data as an embeddable HTML artifact.</div>
    <table>
      <thead><tr>{headers}</tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </main>
</body>
</html>
"""
        path.write_text(html, encoding="utf-8")

    def _chart_title(self, chart_type: str, mapping: dict[str, str]) -> str:
        labels = {
            "line": "趋势图",
            "bar": "对比柱状图",
            "pie": "占比饼图",
            "scatter": "相关散点图",
            "heatmap": "热力图",
        }
        fields = ", ".join(mapping.values())
        return f"{labels.get(chart_type, '图表')} - {fields}"

    def _fallback_table(self, dataframe: pd.DataFrame, month_column: str | None, sales_column: str | None) -> list[dict[str, Any]]:
        columns = [column for column in [month_column, sales_column] if column]
        if not columns:
            columns = list(dataframe.columns[:5])
        cleaned = dataframe[columns].head(10).astype(object).where(pd.notna(dataframe[columns].head(10)), None)
        return cleaned.to_dict(orient="records")

    def _find_column(self, dataframe: pd.DataFrame, candidates: list[str]) -> str | None:
        lowered = {str(column).lower(): str(column) for column in dataframe.columns}
        for candidate in candidates:
            candidate_lower = candidate.lower()
            for lowered_name, original_name in lowered.items():
                if candidate_lower in lowered_name:
                    return original_name
        return None

    def _numeric_columns(self, dataframe: pd.DataFrame) -> list[str]:
        columns: list[str] = []
        for column in dataframe.columns:
            if pd.api.types.is_numeric_dtype(dataframe[column]):
                columns.append(str(column))
                continue
            converted = pd.to_numeric(dataframe[column], errors="coerce")
            if converted.notna().sum() >= max(1, len(dataframe) * 0.6):
                columns.append(str(column))
        return columns

    def _date_columns(self, dataframe: pd.DataFrame) -> list[str]:
        columns: list[str] = []
        date_tokens = ["date", "month", "time", "日期", "月份", "时间", "月"]
        for column in dataframe.columns:
            name = str(column)
            lowered = name.lower()
            if any(token in lowered for token in date_tokens):
                columns.append(name)
                continue
            if pd.api.types.is_datetime64_any_dtype(dataframe[column]):
                columns.append(name)
        return columns

    def _categorical_columns(self, dataframe: pd.DataFrame) -> list[str]:
        numeric_columns = set(self._numeric_columns(dataframe))
        return [str(column) for column in dataframe.columns if str(column) not in numeric_columns]

    def _first(self, *groups: Any) -> str | None:
        for group in groups:
            for item in list(group):
                if item is not None:
                    return str(item)
        return None

    def _compact_mapping(self, mapping: dict[str, str | None]) -> dict[str, str]:
        return {key: value for key, value in mapping.items() if value}

    def _html_escape(self, value: Any) -> str:
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )
