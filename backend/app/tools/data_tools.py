from __future__ import annotations

from time import perf_counter
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from app.data_sources.registry import DataSourceRegistry
from app.schemas.chat import AnalysisResult, ChartArtifact
from app.services.chart_service import ChartService
from app.services.dataset_store import DatasetNotFoundError, DatasetParseError, DatasetStore
from app.services.pandasai_service import PandasAIService, PandasAIServiceError
from app.services.report_service import ReportService


TEXT_REPORT_FALLBACK_TITLE = "数据分析报告"
TEXT_REPORT_FALLBACK_SUMMARY = "报告导出失败，已降级为 Markdown 摘要。"


class ToolExecutionResult(BaseModel):
    tool_name: str
    status: str
    payload: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    error_message: str | None = None
    duration_ms: int = 0


class DataAgentTools:
    def __init__(
        self,
        dataset_store: DatasetStore | None = None,
        pandasai_service: PandasAIService | None = None,
        chart_service: ChartService | None = None,
        report_service: ReportService | None = None,
    ) -> None:
        self.dataset_store = dataset_store or DatasetStore()
        self.data_source_registry = DataSourceRegistry(self.dataset_store)
        self.pandasai_service = pandasai_service or PandasAIService()
        self.chart_service = chart_service or ChartService(self.dataset_store.base_dir)
        self.report_service = report_service or ReportService(
            dataset_store=self.dataset_store,
            base_dir=self.dataset_store.base_dir,
        )

    def dataset_overview(self, dataset_id: str) -> ToolExecutionResult:
        started_at = perf_counter()
        try:
            dataframe = self.dataset_store.load_dataframe(dataset_id)
            schema = self.dataset_store.load_schema(dataset_id)
            preview = self._records(dataframe.head(10))
            quality_summary = {
                "missing_cells": int(dataframe.isna().sum().sum()),
                "duplicate_rows": int(dataframe.duplicated().sum()),
                "memory_usage_bytes": int(dataframe.memory_usage(deep=True).sum()),
            }
            schema_rows = [
                {
                    "name": column.name,
                    "dtype": column.dtype,
                    "missing_count": column.missing_count,
                    "missing_ratio": column.missing_ratio,
                }
                for column in schema
            ]
            markdown = self._dataset_overview_markdown(dataset_id, dataframe, schema_rows, quality_summary)
            result = AnalysisResult(type="markdown", value=markdown, summary=f"数据集包含 {len(dataframe)} 行、{len(dataframe.columns)} 列。")
            return self._result(
                tool_name="dataset_overview",
                status="success",
                started_at=started_at,
                payload={
                    "analysis_result": result,
                    "dataset_id": dataset_id,
                    "rows": len(dataframe),
                    "columns": len(dataframe.columns),
                    "schema": schema_rows,
                    "preview": preview,
                    "quality_summary": quality_summary,
                },
            )
        except (DatasetNotFoundError, DatasetParseError) as exc:
            return self._result(
                tool_name="dataset_overview",
                status="error",
                started_at=started_at,
                error_message=str(exc),
            )
        except Exception as exc:
            return self._result(
                tool_name="dataset_overview",
                status="error",
                started_at=started_at,
                error_message=f"dataset_overview tool failed: {exc}",
            )

    def cleaning_advice(self, dataset_id: str) -> ToolExecutionResult:
        started_at = perf_counter()
        try:
            dataframe = self.dataset_store.load_dataframe(dataset_id)
            schema = self.dataset_store.load_schema(dataset_id)
            missing_cells = int(dataframe.isna().sum().sum())
            duplicate_rows = int(dataframe.duplicated().sum())
            missing_columns = [column for column in schema if column.missing_count > 0]
            object_columns = [column.name for column in schema if "object" in column.dtype.lower()]
            numeric_like_columns = [
                column
                for column in object_columns
                if pd.to_numeric(dataframe[column], errors="coerce").notna().sum() >= max(1, len(dataframe) * 0.6)
            ]
            lines = [
                "# 数据质量与清洗建议",
                "",
                f"- 数据规模：{len(dataframe)} 行，{len(dataframe.columns)} 列。",
                f"- 缺失单元格：{missing_cells}。",
                f"- 重复行：{duplicate_rows}。",
                "",
                "## 建议",
            ]
            if missing_columns:
                names = "、".join(column.name for column in missing_columns[:8])
                lines.append(f"- 优先处理缺失值字段：{names}。可按业务含义选择删除、均值/中位数填充或标记为未知。")
            else:
                lines.append("- 暂未发现缺失值，可以继续检查异常值和字段类型。")
            if duplicate_rows:
                lines.append("- 存在重复行，建议先按主键或全字段去重，再进行聚合分析。")
            else:
                lines.append("- 暂未发现重复行。")
            if numeric_like_columns:
                lines.append(f"- 以下字段看起来像数值但当前可能是文本：{'、'.join(numeric_like_columns[:8])}，建议转换为数值类型。")
            lines.append("- 对日期、月份、地区、产品等维度字段统一格式，便于 SQL 查询和图表生成。")
            markdown = "\n".join(lines)
            result = AnalysisResult(type="markdown", value=markdown, summary="已生成数据质量与清洗建议。")
            return self._result(
                tool_name="cleaning_advice",
                status="success",
                started_at=started_at,
                payload={
                    "analysis_result": result,
                    "dataset_id": dataset_id,
                    "missing_cells": missing_cells,
                    "duplicate_rows": duplicate_rows,
                },
            )
        except (DatasetNotFoundError, DatasetParseError) as exc:
            return self._result(
                tool_name="cleaning_advice",
                status="error",
                started_at=started_at,
                error_message=str(exc),
            )
        except Exception as exc:
            return self._result(
                tool_name="cleaning_advice",
                status="error",
                started_at=started_at,
                error_message=f"cleaning_advice tool failed: {exc}",
            )

    def analyze_table(self, dataset_id: str, question: str, session_id: str = "sess_demo") -> ToolExecutionResult:
        started_at = perf_counter()
        try:
            dataframe = self.dataset_store.load_dataframe(dataset_id)
            schema = self.dataset_store.load_schema(dataset_id)
            result = self.pandasai_service.analyze(dataframe, question, schema)
            return self._result(
                tool_name="analyze_table",
                status="success",
                started_at=started_at,
                payload={
                    "analysis_result": result,
                    "session_id": session_id,
                    "dataset_id": dataset_id,
                    "rows": len(dataframe),
                    "columns": len(dataframe.columns),
                },
            )
        except (DatasetNotFoundError, DatasetParseError, PandasAIServiceError) as exc:
            return self._result(
                tool_name="analyze_table",
                status="error",
                started_at=started_at,
                error_message=str(exc),
            )
        except Exception as exc:
            return self._result(
                tool_name="analyze_table",
                status="error",
                started_at=started_at,
                error_message=f"analyze_table 工具调用失败：{exc}",
            )

    def query_dataset(self, dataset_id: str, sql: str) -> ToolExecutionResult:
        started_at = perf_counter()
        try:
            data_source = self.data_source_registry.get(dataset_id)
            dataframe, error = data_source.execute_query(sql)
            if error:
                return self._result(
                    tool_name="query_dataset",
                    status="error",
                    started_at=started_at,
                    payload={"dataset_id": dataset_id, "sql": sql},
                    error_message=f"SQL query failed: {error}",
                )

            cleaned = dataframe.astype(object).where(pd.notna(dataframe), None)
            records = cleaned.to_dict(orient="records")
            result = AnalysisResult(
                type="dataframe",
                value=records,
                summary=f"SQL query returned {len(dataframe)} rows and {len(dataframe.columns)} columns.",
            )
            return self._result(
                tool_name="query_dataset",
                status="success",
                started_at=started_at,
                payload={
                    "analysis_result": result,
                    "dataset_id": dataset_id,
                    "sql": sql,
                    "rows": len(dataframe),
                    "columns": len(dataframe.columns),
                },
            )
        except (DatasetNotFoundError, DatasetParseError) as exc:
            return self._result(
                tool_name="query_dataset",
                status="error",
                started_at=started_at,
                payload={"dataset_id": dataset_id, "sql": sql},
                error_message=str(exc),
            )
        except Exception as exc:
            return self._result(
                tool_name="query_dataset",
                status="error",
                started_at=started_at,
                payload={"dataset_id": dataset_id, "sql": sql},
                error_message=f"query_dataset tool failed: {exc}",
            )

    def build_chart(self, dataset_id: str, question: str, chart_type: str = "trend") -> ToolExecutionResult:
        started_at = perf_counter()
        try:
            dataframe = self.dataset_store.load_dataframe(dataset_id)
            requested_chart_type = None if chart_type == "trend" else chart_type
            result, charts, warnings = self.chart_service.build_chart(dataframe, question, requested_chart_type)
            fallback_used = bool(warnings) or not charts
            return self._result(
                tool_name="build_chart",
                status="warning" if warnings else "success",
                started_at=started_at,
                payload={"analysis_result": result, "charts": charts, "chart_type": charts[0].type if charts else requested_chart_type},
                warnings=warnings,
                fallback_used=fallback_used,
            )
            if chart_type != "trend":
                fallback = dataframe.head(10).astype(object).where(dataframe.head(10).notna(), None)
                return self._result(
                    tool_name="build_chart",
                    status="warning",
                    started_at=started_at,
                    payload={
                        "analysis_result": AnalysisResult(
                            type="dataframe",
                            value=fallback.to_dict(orient="records"),
                            summary=f"暂不支持 {chart_type} 图表，已降级为表格结果。",
                        ),
                        "charts": [],
                    },
                    warnings=[f"暂不支持 {chart_type} 图表，已降级为表格结果。"],
                    fallback_used=True,
                )

            result, charts, warnings = self.chart_service.build_trend_chart(dataframe, question)
            fallback_used = bool(warnings) or not charts
            return self._result(
                tool_name="build_chart",
                status="warning" if warnings else "success",
                started_at=started_at,
                payload={"analysis_result": result, "charts": charts, "chart_type": chart_type},
                warnings=warnings,
                fallback_used=fallback_used,
            )
        except (DatasetNotFoundError, DatasetParseError) as exc:
            return self._result(
                tool_name="build_chart",
                status="error",
                started_at=started_at,
                error_message=str(exc),
            )
        except Exception as exc:
            return self._result(
                tool_name="build_chart",
                status="error",
                started_at=started_at,
                error_message=f"build_chart 工具调用失败：{exc}",
            )

    def export_report(
        self,
        session_id: str,
        dataset_id: str | None = None,
        analysis_summary: str | None = None,
        chart_urls: list[str] | None = None,
    ) -> ToolExecutionResult:
        started_at = perf_counter()
        try:
            markdown = self.report_service.generate_markdown(session_id, dataset_id=dataset_id)
            markdown = self._append_report_context(markdown, analysis_summary, chart_urls)
            return self._result(
                tool_name="export_report",
                status="success",
                started_at=started_at,
                payload={
                    "report_markdown": markdown,
                    "session_id": session_id,
                    "dataset_id": dataset_id,
                },
            )
        except Exception as exc:
            markdown = self._fallback_report(session_id, dataset_id, analysis_summary, chart_urls)
            return self._result(
                tool_name="export_report",
                status="warning",
                started_at=started_at,
                payload={
                    "report_markdown": markdown,
                    "session_id": session_id,
                    "dataset_id": dataset_id,
                },
                warnings=[TEXT_REPORT_FALLBACK_SUMMARY],
                fallback_used=True,
                error_message=str(exc),
            )

    def _append_report_context(
        self,
        markdown: str,
        analysis_summary: str | None,
        chart_urls: list[str] | None,
    ) -> str:
        extras: list[str] = []
        if analysis_summary:
            extras.extend(["", "## 本次工具链摘要", "", f"- 分析结论：{analysis_summary}"])
        if chart_urls:
            extras.append(f"- 图表产物：{', '.join(chart_urls)}")
        if not extras:
            return markdown
        return markdown.rstrip() + "\n" + "\n".join(extras) + "\n"

    def _fallback_report(
        self,
        session_id: str,
        dataset_id: str | None,
        analysis_summary: str | None,
        chart_urls: list[str] | None,
    ) -> str:
        lines = [
            f"# {TEXT_REPORT_FALLBACK_TITLE}",
            "",
            "## 降级说明",
            "",
            TEXT_REPORT_FALLBACK_SUMMARY,
            "",
            "## 上下文",
            "",
            f"- Session ID: `{session_id}`",
            f"- Dataset ID: `{dataset_id or '-'}`",
        ]
        if analysis_summary:
            lines.append(f"- 分析结论：{analysis_summary}")
        if chart_urls:
            lines.append(f"- 图表产物：{', '.join(chart_urls)}")
        lines.append("")
        return "\n".join(lines)

    def _records(self, dataframe: pd.DataFrame) -> list[dict[str, Any]]:
        cleaned = dataframe.astype(object).where(pd.notna(dataframe), None)
        return [{str(key): value for key, value in record.items()} for record in cleaned.to_dict(orient="records")]

    def _dataset_overview_markdown(
        self,
        dataset_id: str,
        dataframe: pd.DataFrame,
        schema_rows: list[dict[str, Any]],
        quality_summary: dict[str, int],
    ) -> str:
        lines = [
            "# 数据集概况",
            "",
            f"- Dataset ID: `{dataset_id}`",
            f"- 行数：{len(dataframe)}",
            f"- 列数：{len(dataframe.columns)}",
            f"- 缺失单元格：{quality_summary['missing_cells']}",
            f"- 重复行：{quality_summary['duplicate_rows']}",
            "",
            "## 字段",
            "",
            "| 字段 | 类型 | 缺失数 | 缺失率 |",
            "| --- | --- | ---: | ---: |",
        ]
        for column in schema_rows:
            lines.append(
                f"| {column['name']} | {column['dtype']} | {column['missing_count']} | {column['missing_ratio']:.2%} |"
            )
        lines.extend(["", "## 预览", "", "已返回前 10 行预览，可在表格面板查看。"])
        return "\n".join(lines)

    def _result(
        self,
        *,
        tool_name: str,
        status: str,
        started_at: float,
        payload: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
        fallback_used: bool = False,
        error_message: str | None = None,
    ) -> ToolExecutionResult:
        return ToolExecutionResult(
            tool_name=tool_name,
            status=status,
            payload=payload or {},
            warnings=warnings or [],
            fallback_used=fallback_used,
            error_message=error_message,
            duration_ms=max(0, round((perf_counter() - started_at) * 1000)),
        )
