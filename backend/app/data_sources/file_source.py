from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

from app.data_sources.base import DataSource
from app.data_sources.sqlite_source import MAIN_TABLE, SQLiteDataSource

if TYPE_CHECKING:
    from app.services.dataset_store import DatasetStore


class FileDataSource(DataSource):
    def __init__(self, dataset_id: str, dataset_store: "DatasetStore") -> None:
        self.dataset_id = dataset_id
        self.dataset_store = dataset_store
        self.name = dataset_id
        self.sqlite_source = SQLiteDataSource(
            dataset_store.sqlite_path(dataset_id),
            name=dataset_id,
        )
        self.ensure_initialized()

    def ensure_initialized(self) -> None:
        if MAIN_TABLE in self.sqlite_source.list_tables():
            return
        dataframe = self.dataset_store.load_dataframe(self.dataset_id)
        self.sqlite_source.initialize_from_dataframe(dataframe, MAIN_TABLE)

    def get_schema(self) -> str:
        return self.sqlite_source.get_schema()

    def execute_query(self, sql: str) -> tuple[pd.DataFrame, str]:
        return self.sqlite_source.execute_query(sql)

    def get_preview(self) -> list[dict[str, Any]]:
        return self.sqlite_source.get_preview()

    def get_preview_table(self, table_name: str, max_rows: int = 100) -> dict[str, Any]:
        return self.sqlite_source.get_preview_table(table_name, max_rows)

    def create_analysis_table(self, sql: str, table_name: str = "analysis_data") -> str:
        return self.sqlite_source.create_analysis_table(sql, table_name)

    def list_tables(self) -> list[str]:
        return self.sqlite_source.list_tables()
