from typing import TypedDict

import pandas as pd

from app.schemas.chat import AgentTraceStep, AnalysisResult, ChartArtifact
from app.schemas.dataset import ColumnSchema


class DataAnalysisState(TypedDict, total=False):
    session_id: str
    dataset_id: str
    message: str
    resolved_message: str
    command_name: str
    command_args: str
    tool_route: str
    query_mode: str
    sql: str
    sql_result_rows: int
    sql_result_columns: int
    dataframe: pd.DataFrame
    dataset_schema: list[ColumnSchema]
    analysis_result: AnalysisResult
    answer: str
    charts: list[ChartArtifact]
    warnings: list[str]
    errors: list[str]
    trace_steps: list[AgentTraceStep]
