from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from app.data_sources.base import DataSource


MAIN_TABLE = "main_table"


def quote_identifier(identifier: str) -> str:
    return '"' + str(identifier).replace('"', '""') + '"'


class SQLiteDataSource(DataSource):
    def __init__(self, db_path: Path, name: str = "SQLite dataset") -> None:
        self.db_path = db_path
        self.name = name
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def initialize_from_dataframe(self, dataframe: pd.DataFrame, table_name: str = MAIN_TABLE) -> None:
        normalized = dataframe.copy()
        normalized.columns = [str(column) for column in normalized.columns]
        with sqlite3.connect(self.db_path) as conn:
            normalized.to_sql(table_name, conn, if_exists="replace", index=False)

    def get_schema(self) -> str:
        parts: list[str] = []
        with sqlite3.connect(self.db_path) as conn:
            for table in self.list_tables():
                columns = conn.execute(f"PRAGMA table_info({quote_identifier(table)})").fetchall()
                count_row = conn.execute(f"SELECT COUNT(*) FROM {quote_identifier(table)}").fetchone()
                rows = int(count_row[0]) if count_row else 0
                lines = [f"Table: {table} ({rows} rows)"]
                for column in columns:
                    lines.append(f"  {column[1]} {column[2] or 'TEXT'}")
                parts.append("\n".join(lines))
        return "\n\n".join(parts)

    def execute_query(self, sql: str) -> tuple[pd.DataFrame, str]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                dataframe = pd.read_sql_query(sql, conn)
            return dataframe, ""
        except Exception as exc:
            return pd.DataFrame(), str(exc)

    def get_preview(self) -> list[dict[str, Any]]:
        preview: list[dict[str, Any]] = []
        with sqlite3.connect(self.db_path) as conn:
            for table in self.list_tables():
                columns = conn.execute(f"PRAGMA table_info({quote_identifier(table)})").fetchall()
                count_row = conn.execute(f"SELECT COUNT(*) FROM {quote_identifier(table)}").fetchone()
                preview.append(
                    {
                        "name": table,
                        "columns": [str(column[1]) for column in columns],
                        "total_rows": int(count_row[0]) if count_row else 0,
                    }
                )
        return preview

    def get_preview_table(self, table_name: str, max_rows: int = 100) -> dict[str, Any]:
        limit = max(1, min(int(max_rows), 1000))
        with sqlite3.connect(self.db_path) as conn:
            dataframe = pd.read_sql_query(
                f"SELECT * FROM {quote_identifier(table_name)} LIMIT {limit}",
                conn,
            )
            count_row = conn.execute(f"SELECT COUNT(*) FROM {quote_identifier(table_name)}").fetchone()
        cleaned = dataframe.astype(object).where(pd.notna(dataframe), None)
        return {
            "name": table_name,
            "columns": [str(column) for column in dataframe.columns],
            "rows": cleaned.values.tolist(),
            "total_rows": int(count_row[0]) if count_row else 0,
        }

    def create_analysis_table(self, sql: str, table_name: str = "analysis_data") -> str:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(f"DROP TABLE IF EXISTS {quote_identifier(table_name)}")
                conn.execute(
                    f"CREATE TABLE {quote_identifier(table_name)} AS {sql.strip().rstrip(';')}"
                )
                count_row = conn.execute(f"SELECT COUNT(*) FROM {quote_identifier(table_name)}").fetchone()
            return f"Table: {table_name} ({int(count_row[0]) if count_row else 0} rows)"
        except Exception as exc:
            return f"Error building analysis table: {exc}"

    def list_tables(self) -> list[str]:
        if not self.db_path.exists():
            return []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        return [str(row[0]) for row in rows]
