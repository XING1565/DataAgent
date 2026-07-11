from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class DataSource(ABC):
    name: str

    @abstractmethod
    def get_schema(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def execute_query(self, sql: str) -> tuple[pd.DataFrame, str]:
        raise NotImplementedError

    def get_preview(self) -> list[dict[str, Any]]:
        return []

    def get_preview_table(self, table_name: str, max_rows: int = 100) -> dict[str, Any]:
        return {"name": table_name, "columns": [], "rows": [], "total_rows": 0}

    @abstractmethod
    def create_analysis_table(self, sql: str, table_name: str = "analysis_data") -> str:
        raise NotImplementedError

    @abstractmethod
    def list_tables(self) -> list[str]:
        raise NotImplementedError
