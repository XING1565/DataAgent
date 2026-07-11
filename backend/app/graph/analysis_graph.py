from __future__ import annotations

from time import perf_counter
from typing import Any, Iterator

from langgraph.graph import END, START, StateGraph

from app.commands.dispatcher import dispatch_command
from app.graph.state import DataAnalysisState
from app.schemas.chat import AgentTraceStep, AnalysisResult, ChatResponse
from app.services.chart_service import ChartService
from app.services.dataset_store import DatasetNotFoundError, DatasetParseError, DatasetStore
from app.services.pandasai_service import PandasAIService
from app.services.report_service import ReportService, TEXT_REPORT_SUMMARY, is_report_request
from app.services.session_store import SessionStore
from app.tools.data_tools import DataAgentTools, ToolExecutionResult


class AnalysisGraph:
    def __init__(
        self,
        dataset_store: DatasetStore | None = None,
        pandasai_service: PandasAIService | None = None,
        chart_service: ChartService | None = None,
        report_service: ReportService | None = None,
        data_tools: DataAgentTools | None = None,
        session_store: SessionStore | None = None,
    ) -> None:
        self.dataset_store = dataset_store or DatasetStore()
        self.pandasai_service = pandasai_service or PandasAIService()
        self.chart_service = chart_service or ChartService(self.dataset_store.base_dir)
        self.session_store = session_store or SessionStore(self.dataset_store.base_dir)
        self.report_service = report_service or ReportService(
            session_store=self.session_store,
            dataset_store=self.dataset_store,
            base_dir=self.dataset_store.base_dir,
        )
        self.data_tools = data_tools or DataAgentTools(
            dataset_store=self.dataset_store,
            pandasai_service=self.pandasai_service,
            chart_service=self.chart_service,
            report_service=self.report_service,
        )
        self.graph = self._build_graph()

    def run(self, session_id: str, dataset_id: str, message: str) -> ChatResponse:
        final_state = self.graph.invoke(self._initial_state(session_id, dataset_id, message))
        return self._response_from_state(session_id, dataset_id, final_state)

    def stream(self, session_id: str, dataset_id: str, message: str) -> Iterator[dict[str, Any]]:
        final_state: DataAnalysisState | None = None
        seen_trace_steps = 0
        try:
            for state in self.graph.stream(
                self._initial_state(session_id, dataset_id, message),
                stream_mode="values",
            ):
                final_state = state
                trace_steps = list(state.get("trace_steps", []))
                for trace_step in trace_steps[seen_trace_steps:]:
                    yield {
                        "type": "step_started",
                        "step": trace_step.step,
                        "message": self._step_message(trace_step.step),
                    }
                    yield {
                        "type": "step_finished",
                        "step": trace_step.step,
                        "status": trace_step.status,
                        "duration_ms": trace_step.duration_ms,
                        "trace_step": trace_step.model_dump(),
                    }
                seen_trace_steps = len(trace_steps)

            if final_state is None:
                raise RuntimeError("Analysis graph did not produce a final state.")

            response = self._response_from_state(session_id, dataset_id, final_state)
            yield {"type": "text", "content": response.answer or response.result.summary}
            for chart in response.charts:
                yield {"type": "chart", "chart": chart.model_dump()}
            yield {"type": "response", "response": response.model_dump()}
        except Exception as exc:
            yield {"type": "error", "message": str(exc)}
        finally:
            yield {"type": "done"}

    def _initial_state(self, session_id: str, dataset_id: str, message: str) -> DataAnalysisState:
        return {
            "session_id": session_id,
            "dataset_id": dataset_id,
            "message": message,
            "resolved_message": message,
            "charts": [],
            "warnings": [],
            "errors": [],
            "trace_steps": [],
        }

    def _response_from_state(self, session_id: str, dataset_id: str, final_state: DataAnalysisState) -> ChatResponse:
        result = final_state["analysis_result"]
        return ChatResponse(
            session_id=session_id,
            dataset_id=dataset_id,
            answer=final_state.get("answer", result.summary),
            result=result,
            charts=final_state.get("charts", []),
            warnings=final_state.get("warnings", []),
            errors=final_state.get("errors", []),
            trace_steps=final_state.get("trace_steps", []),
        )

    def _step_message(self, step: str) -> str:
        labels = {
            "load_dataset": "正在加载数据集",
            "resolve_context": "正在解析上下文",
            "detect_command": "正在识别命令",
            "dataset_overview_tool": "正在生成数据概况",
            "data_cleaning_tool": "正在生成清洗建议",
            "plan_query": "正在规划 SQL 查询",
            "execute_query_tool": "正在执行 SQL 查询",
            "analyze_query_result": "正在整理查询结果",
            "analyze_table_tool": "正在执行表格分析",
            "build_chart_tool": "正在生成图表",
            "export_report_tool": "正在生成报告",
            "save_session": "正在保存会话",
            "finalize": "正在整理最终响应",
        }
        return labels.get(step, f"正在执行 {step}")

    def _build_graph(self):
        workflow = StateGraph(DataAnalysisState)
        workflow.add_node("load_dataset", self._load_dataset_node)
        workflow.add_node("resolve_context", self._resolve_context_node)
        workflow.add_node("detect_command", self._detect_command_node)
        workflow.add_node("dataset_overview_tool", self._dataset_overview_tool_node)
        workflow.add_node("data_cleaning_tool", self._data_cleaning_tool_node)
        workflow.add_node("plan_query", self._plan_query_node)
        workflow.add_node("execute_query_tool", self._execute_query_tool_node)
        workflow.add_node("analyze_query_result", self._analyze_query_result_node)
        workflow.add_node("analyze_table_tool", self._analyze_table_tool_node)
        workflow.add_node("build_chart_tool", self._build_chart_tool_node)
        workflow.add_node("export_report_tool", self._export_report_tool_node)
        workflow.add_node("save_session", self._save_session_node)
        workflow.add_node("finalize", self._finalize_node)
        workflow.add_edge(START, "load_dataset")
        workflow.add_edge("load_dataset", "resolve_context")
        workflow.add_conditional_edges(
            "detect_command",
            self._route_tool,
            {
                "data": "dataset_overview_tool",
                "clean": "data_cleaning_tool",
                "sql": "plan_query",
                "chart": "build_chart_tool",
                "report": "export_report_tool",
                "analysis": "analyze_table_tool",
                "finish": "save_session",
            },
        )
        workflow.add_edge("resolve_context", "detect_command")
        workflow.add_edge("dataset_overview_tool", "save_session")
        workflow.add_edge("data_cleaning_tool", "save_session")
        workflow.add_edge("plan_query", "execute_query_tool")
        workflow.add_edge("execute_query_tool", "analyze_query_result")
        workflow.add_edge("analyze_query_result", "build_chart_tool")
        workflow.add_edge("analyze_table_tool", "build_chart_tool")
        workflow.add_edge("build_chart_tool", "export_report_tool")
        workflow.add_edge("export_report_tool", "save_session")
        workflow.add_edge("save_session", "finalize")
        workflow.add_edge("finalize", END)
        return workflow.compile()

    def _load_dataset_node(self, state: DataAnalysisState) -> DataAnalysisState:
        started_at = perf_counter()
        errors = list(state.get("errors", []))
        details: dict[str, Any] = {"dataset_id": state["dataset_id"]}
        try:
            dataframe = self.dataset_store.load_dataframe(state["dataset_id"])
            schema = self.dataset_store.load_schema(state["dataset_id"])
            details.update({"rows": len(dataframe), "columns": len(dataframe.columns)})
            output: DataAnalysisState = {"dataframe": dataframe, "dataset_schema": schema, "errors": errors}
            return self._with_trace(
                state,
                output,
                step="load_dataset",
                status="success",
                started_at=started_at,
                observation=f"Loaded dataset with {len(dataframe)} rows and {len(dataframe.columns)} columns.",
                thought="Inspect the uploaded table before planning analysis.",
                action="load dataframe and schema",
                tool="DatasetStore.load_dataframe",
                details=details,
            )
        except (DatasetNotFoundError, DatasetParseError) as exc:
            if is_report_request(state["message"]) or state["message"].strip().lower().startswith("/report"):
                warnings = list(state.get("warnings", []))
                warnings.append(str(exc))
                return self._with_trace(
                    state,
                    {"errors": errors, "warnings": warnings},
                    step="load_dataset",
                    status="warning",
                    started_at=started_at,
                    observation=str(exc),
                    thought="Report export can still produce a readable Markdown fallback without a loaded dataframe.",
                    action="continue to report export fallback",
                    tool="DatasetStore.load_dataframe",
                    details=details,
                    fallback_used=True,
                    error_message=str(exc),
                )
            errors.append(str(exc))
            output = {"errors": errors}
            return self._with_trace(
                state,
                output,
                step="load_dataset",
                status="error",
                started_at=started_at,
                observation=str(exc),
                thought="Dataset loading failed, so downstream analysis should stop.",
                action="return readable dataset error",
                tool="DatasetStore.load_dataframe",
                details=details,
            )

    def _resolve_context_node(self, state: DataAnalysisState) -> DataAnalysisState:
        started_at = perf_counter()
        errors = list(state.get("errors", []))
        if errors:
            return self._with_trace(
                state,
                {"errors": errors},
                step="resolve_context",
                status="skipped",
                started_at=started_at,
                observation="Skipped context resolution because an earlier step failed.",
                thought="Preserve the original error and avoid additional tool calls.",
                action="skip context resolver",
            )

        resolved_message = self.session_store.resolve_message(state["session_id"], state["message"])
        changed = resolved_message != state["message"]
        return self._with_trace(
            state,
            {"resolved_message": resolved_message, "errors": errors},
            step="resolve_context",
            status="success",
            started_at=started_at,
            observation="Resolved follow-up context from session history." if changed else "Question is self-contained.",
            thought="Use recent session turns to make ambiguous follow-up questions explicit.",
            action="resolve user message",
            tool="SessionStore.resolve_message",
            details={"message_changed": changed},
        )

    def _detect_command_node(self, state: DataAnalysisState) -> DataAnalysisState:
        started_at = perf_counter()
        errors = list(state.get("errors", []))
        if errors:
            return self._with_trace(
                state,
                {"errors": errors, "tool_route": "finish"},
                step="detect_command",
                status="skipped",
                started_at=started_at,
                observation="Skipped command detection because an earlier step failed.",
                thought="Preserve the original error and route to finalization.",
                action="skip command detection",
            )

        dispatch = dispatch_command(state["message"])
        output: DataAnalysisState = {"tool_route": dispatch.route, "errors": errors}
        details: dict[str, Any] = {"route": dispatch.route}
        if dispatch.command:
            output["command_name"] = dispatch.command.name
            output["command_args"] = dispatch.command.args
            details.update({"command": dispatch.command.name, "args": dispatch.command.args})
        if dispatch.resolved_message:
            output["resolved_message"] = dispatch.resolved_message
        if dispatch.error_message:
            errors.append(dispatch.error_message)
            output["errors"] = errors
            output["tool_route"] = "finish"
            return self._with_trace(
                state,
                output,
                step="detect_command",
                status="error",
                started_at=started_at,
                observation=dispatch.error_message,
                thought="Unknown slash command should return a readable command hint.",
                action="return command error",
                details=details,
                error_message=dispatch.error_message,
            )

        if dispatch.command:
            return self._with_trace(
                state,
                output,
                step="detect_command",
                status="success",
                started_at=started_at,
                observation=f"Detected command /{dispatch.command.name}.",
                thought="Use deterministic command routing before natural-language analysis.",
                action="route slash command",
                details=details,
            )

        return self._with_trace(
            state,
            output,
            step="detect_command",
            status="skipped",
            started_at=started_at,
            observation="No slash command detected.",
            thought="Continue with the standard analysis router.",
            action="continue normal routing",
            details=details,
        )

    def _dataset_overview_tool_node(self, state: DataAnalysisState) -> DataAnalysisState:
        started_at = perf_counter()
        errors = list(state.get("errors", []))
        if errors:
            return self._with_trace(
                state,
                {"errors": errors},
                step="dataset_overview_tool",
                status="skipped",
                started_at=started_at,
                observation="Skipped dataset overview because an earlier step failed.",
                thought="Avoid extra tool calls when required context is invalid.",
                action="skip dataset_overview",
            )

        tool_result = self.data_tools.dataset_overview(state["dataset_id"])
        result = tool_result.payload.get("analysis_result")
        output: DataAnalysisState = {"errors": errors}
        if isinstance(result, AnalysisResult):
            output["analysis_result"] = result
            output["answer"] = result.summary
        if tool_result.status == "error":
            errors.append(tool_result.error_message or "dataset_overview failed.")
            output["errors"] = errors

        return self._with_trace(
            state,
            output,
            step="dataset_overview_tool",
            status=tool_result.status,
            started_at=started_at,
            observation=tool_result.error_message or "Generated dataset overview.",
            thought="Return deterministic dataset metadata for the /data command.",
            action="call dataset_overview tool",
            tool="dataset_overview",
            details={"rows": tool_result.payload.get("rows"), "columns": tool_result.payload.get("columns")},
            tool_result=tool_result,
            input_summary=self._input_summary("dataset_overview", state),
            output_summary=self._output_summary(tool_result),
        )

    def _data_cleaning_tool_node(self, state: DataAnalysisState) -> DataAnalysisState:
        started_at = perf_counter()
        errors = list(state.get("errors", []))
        if errors:
            return self._with_trace(
                state,
                {"errors": errors},
                step="data_cleaning_tool",
                status="skipped",
                started_at=started_at,
                observation="Skipped cleaning advice because an earlier step failed.",
                thought="Avoid extra tool calls when required context is invalid.",
                action="skip cleaning_advice",
            )

        tool_result = self.data_tools.cleaning_advice(state["dataset_id"])
        result = tool_result.payload.get("analysis_result")
        output: DataAnalysisState = {"errors": errors}
        if isinstance(result, AnalysisResult):
            output["analysis_result"] = result
            output["answer"] = result.summary
        if tool_result.status == "error":
            errors.append(tool_result.error_message or "cleaning_advice failed.")
            output["errors"] = errors

        return self._with_trace(
            state,
            output,
            step="data_cleaning_tool",
            status=tool_result.status,
            started_at=started_at,
            observation=tool_result.error_message or "Generated data cleaning advice.",
            thought="Return deterministic quality checks and cleaning suggestions for the /clean command.",
            action="call cleaning_advice tool",
            tool="cleaning_advice",
            details={
                "missing_cells": tool_result.payload.get("missing_cells"),
                "duplicate_rows": tool_result.payload.get("duplicate_rows"),
            },
            tool_result=tool_result,
            input_summary=self._input_summary("cleaning_advice", state),
            output_summary=self._output_summary(tool_result),
        )

    def _plan_query_node(self, state: DataAnalysisState) -> DataAnalysisState:
        started_at = perf_counter()
        errors = list(state.get("errors", []))
        if errors:
            return self._with_trace(
                state,
                {"errors": errors},
                step="plan_query",
                status="skipped",
                started_at=started_at,
                observation="Skipped SQL planning because an earlier step failed.",
                thought="Avoid preparing SQL when dataset context is invalid.",
                action="skip SQL planner",
            )

        sql = state.get("command_args", "").strip() if state.get("command_name") == "sql" else self._extract_sql(state.get("resolved_message", state["message"]))
        if not sql:
            errors.append("未识别到可执行 SQL，请使用 /sql SELECT ... 或直接输入 SELECT/WITH 查询。")
            return self._with_trace(
                state,
                {"errors": errors, "query_mode": "sql"},
                step="plan_query",
                status="error",
                started_at=started_at,
                observation=errors[-1],
                thought="SQL mode requires an explicit SQL statement in this first stage.",
                action="return SQL planning error",
            )

        return self._with_trace(
            state,
            {"sql": sql, "query_mode": "sql", "errors": errors},
            step="plan_query",
            status="success",
            started_at=started_at,
            observation="Recognized an explicit SQL query.",
            thought="Use the user-provided SQL directly without LLM rewriting.",
            action="prepare SQL query",
            details={"sql": sql},
            input_summary=state.get("resolved_message", state["message"])[:120],
            output_summary=sql[:160],
        )

    def _execute_query_tool_node(self, state: DataAnalysisState) -> DataAnalysisState:
        started_at = perf_counter()
        errors = list(state.get("errors", []))
        if errors:
            return self._with_trace(
                state,
                {"errors": errors},
                step="execute_query_tool",
                status="skipped",
                started_at=started_at,
                observation="Skipped SQL execution because query planning failed.",
                thought="Do not call query_dataset with an invalid SQL state.",
                action="skip query_dataset",
            )

        sql = state.get("sql", "")
        tool_result = self.data_tools.query_dataset(state["dataset_id"], sql)
        result = tool_result.payload.get("analysis_result")
        rows = int(tool_result.payload.get("rows", 0) or 0)
        columns = int(tool_result.payload.get("columns", 0) or 0)
        output: DataAnalysisState = {
            "errors": errors,
            "sql_result_rows": rows,
            "sql_result_columns": columns,
        }
        if isinstance(result, AnalysisResult):
            output["analysis_result"] = result
        if tool_result.status == "error":
            errors.append(tool_result.error_message or "SQL query failed.")
            output["errors"] = errors

        return self._with_trace(
            state,
            output,
            step="execute_query_tool",
            status=tool_result.status,
            started_at=started_at,
            observation=(
                f"SQL query returned {rows} rows and {columns} columns."
                if tool_result.status == "success"
                else tool_result.error_message or "SQL query failed."
            ),
            thought="Run the explicit SQL against the local SQLite copy of the uploaded dataset.",
            action="call query_dataset tool",
            tool="query_dataset",
            details={"sql": sql, "rows": rows, "columns": columns},
            tool_result=tool_result,
            input_summary=self._input_summary("query_dataset", state),
            output_summary=self._output_summary(tool_result),
        )

    def _analyze_query_result_node(self, state: DataAnalysisState) -> DataAnalysisState:
        started_at = perf_counter()
        errors = list(state.get("errors", []))
        if errors:
            return self._with_trace(
                state,
                {"errors": errors},
                step="analyze_query_result",
                status="skipped",
                started_at=started_at,
                observation="Skipped SQL result analysis because execution failed.",
                thought="Let finalize return the SQL error in the standard response shape.",
                action="skip SQL result analysis",
            )

        result = state.get("analysis_result")
        if not isinstance(result, AnalysisResult):
            errors.append("SQL query did not return an analysis result.")
            return self._with_trace(
                state,
                {"errors": errors},
                step="analyze_query_result",
                status="error",
                started_at=started_at,
                observation=errors[-1],
                thought="The query tool succeeded structurally but no normalized result was available.",
                action="return SQL result normalization error",
            )

        return self._with_trace(
            state,
            {"analysis_result": result, "answer": result.summary, "errors": errors},
            step="analyze_query_result",
            status="success",
            started_at=started_at,
            observation=result.summary,
            thought="Use the query result as the current analysis output.",
            action="normalize SQL query result",
            details={
                "sql": state.get("sql", ""),
                "rows": state.get("sql_result_rows", 0),
                "columns": state.get("sql_result_columns", 0),
            },
            output_summary=result.summary,
        )

    def _analyze_table_tool_node(self, state: DataAnalysisState) -> DataAnalysisState:
        started_at = perf_counter()
        errors = list(state.get("errors", []))
        if errors:
            return self._with_trace(
                state,
                {"errors": errors},
                step="analyze_table_tool",
                status="skipped",
                started_at=started_at,
                observation="Skipped analyze_table because the request already has errors.",
                thought="Do not invoke analysis tools when required dataset context is missing.",
                action="skip analysis",
            )

        if self._is_export_only_request(state["message"]):
            return self._with_trace(
                state,
                {"errors": errors},
                step="analyze_table_tool",
                status="skipped",
                started_at=started_at,
                observation="The user asked to export a report, so table analysis is skipped.",
                thought="Use session history and dataset overview for a report-only request.",
                action="skip analyze_table",
                tool="analyze_table",
                input_summary=self._input_summary("analyze_table", state),
            )

        tool_result = self.data_tools.analyze_table(
            dataset_id=state["dataset_id"],
            question=state.get("resolved_message", state["message"]),
            session_id=state["session_id"],
        )
        result = tool_result.payload.get("analysis_result")
        if isinstance(result, AnalysisResult):
            return self._with_trace(
                state,
                {"analysis_result": result, "errors": errors},
                step="analyze_table_tool",
                status=tool_result.status,
                started_at=started_at,
                observation=f"analyze_table produced a {result.type} result.",
                thought="Let the agent decide the task, then delegate deterministic table work to a tool.",
                action="call analyze_table tool",
                tool="analyze_table",
                details={"result_type": result.type},
                tool_result=tool_result,
                input_summary=self._input_summary("analyze_table", state),
                output_summary=self._output_summary(tool_result),
            )

        message = state["message"]
        if self.chart_service.is_chart_request(message) or is_report_request(message):
            warnings = list(state.get("warnings", []))
            if tool_result.error_message:
                warnings.append(tool_result.error_message)
            return self._with_trace(
                state,
                {"errors": errors, "warnings": warnings},
                step="analyze_table_tool",
                status="warning",
                started_at=started_at,
                observation=tool_result.error_message or "analyze_table did not return an analysis result.",
                thought="A chart or report fallback can still produce a useful output.",
                action="continue to downstream fallback",
                tool="analyze_table",
                tool_result=tool_result,
                input_summary=self._input_summary("analyze_table", state),
                output_summary=self._output_summary(tool_result),
            )

        if tool_result.error_message:
            errors.append(tool_result.error_message)
        return self._with_trace(
            state,
            {"errors": errors},
            step="analyze_table_tool",
            status="error",
            started_at=started_at,
            observation=tool_result.error_message or "analyze_table did not return an analysis result.",
            thought="Analysis failed and no downstream fallback applies.",
            action="return analysis error",
            tool="analyze_table",
            tool_result=tool_result,
            input_summary=self._input_summary("analyze_table", state),
            output_summary=self._output_summary(tool_result),
        )

    def _build_chart_tool_node(self, state: DataAnalysisState) -> DataAnalysisState:
        started_at = perf_counter()
        errors = list(state.get("errors", []))
        warnings = list(state.get("warnings", []))
        charts = list(state.get("charts", []))
        if errors:
            return self._with_trace(
                state,
                {"errors": errors, "warnings": warnings, "charts": charts},
                step="build_chart_tool",
                status="skipped",
                started_at=started_at,
                observation="Skipped visualization because an earlier step returned errors.",
                thought="Avoid chart generation when analysis cannot proceed.",
                action="skip visualization",
            )

        message = state["message"]
        if not self.chart_service.is_chart_request(message):
            return self._with_trace(
                state,
                {"errors": errors, "warnings": warnings, "charts": charts},
                step="build_chart_tool",
                status="skipped",
                started_at=started_at,
                observation="The request does not require a chart.",
                thought="Keep the textual or table result from analysis.",
                action="skip chart tool",
            )

        tool_result = self.data_tools.build_chart(
            dataset_id=state["dataset_id"],
            question=state.get("resolved_message", state["message"]),
            chart_type="trend",
        )
        chart_result = tool_result.payload.get("analysis_result")
        chart_artifacts = tool_result.payload.get("charts", [])
        chart_warnings = tool_result.warnings
        warnings.extend(chart_warnings)
        charts.extend(chart_artifacts)
        status = tool_result.status
        output = {
            "charts": charts,
            "warnings": warnings,
            "errors": errors,
        }
        if isinstance(chart_result, AnalysisResult):
            output["analysis_result"] = chart_result
        if tool_result.status == "error":
            errors.append(tool_result.error_message or "build_chart 工具调用失败")
            output["errors"] = errors
        return self._with_trace(
            state,
            output,
            step="build_chart_tool",
            status=status,
            started_at=started_at,
            observation=f"Generated {len(chart_artifacts)} chart artifact(s)." if chart_artifacts else "Chart generation fell back to table output.",
            thought="Use the build_chart tool for visualization and keep table fallback behavior inside the tool.",
            action="call build_chart tool",
            tool="build_chart",
            details={"charts_created": len(chart_artifacts), "warnings": chart_warnings},
            tool_result=tool_result,
            input_summary=self._input_summary("build_chart", state),
            output_summary=self._output_summary(tool_result),
        )

    def _export_report_tool_node(self, state: DataAnalysisState) -> DataAnalysisState:
        started_at = perf_counter()
        errors = list(state.get("errors", []))
        warnings = list(state.get("warnings", []))
        charts = list(state.get("charts", []))

        if state.get("command_name") != "report" and not is_report_request(state["message"]):
            return self._with_trace(
                state,
                {"errors": errors, "warnings": warnings, "charts": charts},
                step="export_report_tool",
                status="skipped",
                started_at=started_at,
                observation="The request does not require a report.",
                thought="Only export reports when the user explicitly asks for one.",
                action="skip export_report",
            )

        if errors:
            return self._with_trace(
                state,
                {"errors": errors, "warnings": warnings, "charts": charts},
                step="export_report_tool",
                status="skipped",
                started_at=started_at,
                observation="Skipped report export because an earlier step returned errors.",
                thought="Avoid hiding a hard failure behind a report artifact.",
                action="skip export_report",
            )

        analysis_result = state.get("analysis_result")
        chart_urls = [chart.url for chart in charts]
        tool_result = self.data_tools.export_report(
            session_id=state["session_id"],
            dataset_id=state.get("dataset_id"),
            analysis_summary=analysis_result.summary if analysis_result else None,
            chart_urls=chart_urls,
        )
        warnings.extend(tool_result.warnings)
        report_markdown = str(tool_result.payload.get("report_markdown") or "")
        result = AnalysisResult(type="markdown", value=report_markdown, summary=TEXT_REPORT_SUMMARY)
        return self._with_trace(
            state,
            {
                "analysis_result": result,
                "answer": report_markdown,
                "charts": charts,
                "warnings": warnings,
                "errors": errors,
            },
            step="export_report_tool",
            status=tool_result.status,
            started_at=started_at,
            observation="Exported a Markdown report." if tool_result.status == "success" else "Report export used Markdown fallback.",
            thought="Turn the current analysis context into a reusable report artifact.",
            action="call export_report tool",
            tool="export_report",
            details={"markdown_length": len(report_markdown), "charts": len(charts)},
            tool_result=tool_result,
            input_summary=self._input_summary("export_report", state),
            output_summary=self._output_summary(tool_result),
        )

    def _save_session_node(self, state: DataAnalysisState) -> DataAnalysisState:
        started_at = perf_counter()
        errors = list(state.get("errors", []))
        warnings = list(state.get("warnings", []))
        charts = list(state.get("charts", []))
        result = state.get("analysis_result")
        summary = result.summary if result else (errors[-1] if errors else "")

        self.session_store.append_turn(
            session_id=state["session_id"],
            dataset_id=state["dataset_id"],
            message=state["message"],
            resolved_message=state.get("resolved_message", state["message"]),
            result_summary=summary,
            charts=charts,
            warnings=warnings,
            errors=errors,
        )
        return self._with_trace(
            state,
            {"errors": errors, "warnings": warnings, "charts": charts},
            step="save_session",
            status="success",
            started_at=started_at,
            observation="Saved this analysis turn to session history.",
            thought="Persist the turn so follow-up questions and reports have context.",
            action="append session turn",
            tool="SessionStore.append_turn",
            details={"charts": len(charts), "warnings": len(warnings), "errors": len(errors)},
        )

    def _finalize_node(self, state: DataAnalysisState) -> DataAnalysisState:
        started_at = perf_counter()
        errors = list(state.get("errors", []))
        if errors:
            result = AnalysisResult(type="error", value=None, summary=errors[-1])
            return self._with_trace(
                state,
                {"analysis_result": result, "answer": errors[-1], "errors": errors},
                step="finalize",
                status="error",
                started_at=started_at,
                observation="Returning the latest error as the assistant answer.",
                thought="Normalize the response shape even when the workflow fails.",
                action="build error ChatResponse payload",
            )

        result = state["analysis_result"]
        return self._with_trace(
            state,
            {"answer": state.get("answer", result.summary), "errors": errors},
            step="finalize",
            status="success",
            started_at=started_at,
            observation="Prepared the final answer for the user.",
            thought="Use the analysis summary as the assistant-facing response.",
            action="build ChatResponse payload",
            details={"result_type": result.type},
        )

    def _is_export_only_request(self, message: str) -> bool:
        normalized = message.strip().lower()
        return normalized in {
            "报告",
            "生成报告",
            "生成分析报告",
            "分析报告",
            "generate report",
            "full report",
            "analysis report",
        }

    def _route_tool(self, state: DataAnalysisState) -> str:
        if state.get("errors"):
            return "finish"
        route = state.get("tool_route")
        if route in {"data", "clean", "sql", "chart", "report"}:
            return route
        if self._extract_sql(state.get("resolved_message", state["message"])):
            return "sql"
        return "analysis"

    def _extract_sql(self, message: str) -> str:
        stripped = message.strip()
        lowered = stripped.lower()
        if lowered.startswith("/sql"):
            return stripped[4:].strip()
        if lowered.startswith("select ") or lowered == "select" or lowered.startswith("with ") or lowered == "with":
            return stripped
        return ""

    def _input_summary(self, tool_name: str, state: DataAnalysisState) -> str:
        if tool_name == "export_report":
            return f"session_id={state['session_id']}, dataset_id={state.get('dataset_id')}"
        if tool_name in {"dataset_overview", "cleaning_advice"}:
            return f"dataset_id={state['dataset_id']}"
        if tool_name == "query_dataset":
            return f"dataset_id={state['dataset_id']}, sql={state.get('sql', '')[:120]}"
        question = state.get("resolved_message", state["message"])
        return f"dataset_id={state['dataset_id']}, question={question[:80]}"

    def _output_summary(self, tool_result: ToolExecutionResult) -> str:
        if tool_result.error_message:
            return tool_result.error_message
        if tool_result.tool_name == "analyze_table":
            result = tool_result.payload.get("analysis_result")
            if isinstance(result, AnalysisResult):
                return f"type={result.type}, summary={result.summary[:120]}"
        if tool_result.tool_name == "dataset_overview":
            return f"rows={tool_result.payload.get('rows', 0)}, columns={tool_result.payload.get('columns', 0)}"
        if tool_result.tool_name == "cleaning_advice":
            return (
                f"missing_cells={tool_result.payload.get('missing_cells', 0)}, "
                f"duplicate_rows={tool_result.payload.get('duplicate_rows', 0)}"
            )
        if tool_result.tool_name == "build_chart":
            charts = tool_result.payload.get("charts", [])
            result = tool_result.payload.get("analysis_result")
            result_type = result.type if isinstance(result, AnalysisResult) else "-"
            return f"charts={len(charts)}, result_type={result_type}, warnings={len(tool_result.warnings)}"
        if tool_result.tool_name == "export_report":
            markdown = str(tool_result.payload.get("report_markdown") or "")
            return f"markdown_length={len(markdown)}, warnings={len(tool_result.warnings)}"
        if tool_result.tool_name == "query_dataset":
            return (
                f"rows={tool_result.payload.get('rows', 0)}, "
                f"columns={tool_result.payload.get('columns', 0)}"
            )
        return f"status={tool_result.status}, warnings={len(tool_result.warnings)}"

    def _with_trace(
        self,
        state: DataAnalysisState,
        output: DataAnalysisState,
        *,
        step: str,
        status: str,
        started_at: float,
        observation: str,
        action: str,
        thought: str = "",
        tool: str = "",
        details: dict[str, Any] | None = None,
        tool_result: ToolExecutionResult | None = None,
        input_summary: str | None = None,
        output_summary: str | None = None,
        fallback_used: bool = False,
        error_message: str | None = None,
    ) -> DataAnalysisState:
        trace_steps = list(state.get("trace_steps", []))
        duration_ms = tool_result.duration_ms if tool_result else max(0, round((perf_counter() - started_at) * 1000))
        trace_steps.append(
            AgentTraceStep(
                step=step,
                status=status,
                duration_ms=duration_ms,
                observation=observation,
                thought=thought,
                action=action,
                tool=tool,
                details=details or {},
                tool_name=tool_result.tool_name if tool_result else (tool or None),
                input_summary=input_summary,
                output_summary=output_summary,
                fallback_used=tool_result.fallback_used if tool_result else fallback_used,
                error_message=tool_result.error_message if tool_result else error_message,
            )
        )
        return {**output, "trace_steps": trace_steps}
