from __future__ import annotations

import pandas as pd

from app.data_sources.base import DataSource


class SQLDataSource(DataSource):
    def __init__(self, *_args, **_kwargs) -> None:
        raise NotImplementedError("External SQL data sources are not implemented in this phase.")

    def get_schema(self) -> str:
        raise NotImplementedError

    def execute_query(self, sql: str) -> tuple[pd.DataFrame, str]:
        raise NotImplementedError

    def create_analysis_table(self, sql: str, table_name: str = "analysis_data") -> str:
        raise NotImplementedError

    def list_tables(self) -> list[str]:
        raise NotImplementedError
